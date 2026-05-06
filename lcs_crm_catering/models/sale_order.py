from odoo import _, api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    CLIENT_TYPE_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
    SETUP_TYPE_SELECTION,
)


# Resolved-prefix → ir.sequence code map.
# Each ir.sequence is created with these codes via data file.
SO_SEQUENCE_PREFIX_MAP = {
    'lacasa': 'lacasa.sale.order',
    'lacasaN': 'lacasaN.sale.order',
    'lacasaE': 'lacasaE.sale.order',
    'lacasaE_N_': 'lacasaE_N_.sale.order',
    'lacasaK': 'lacasaK.sale.order',
    'lacasaFT': 'lacasaFT.sale.order',
    'lacasaW': 'lacasaW.sale.order',
    'lacasaWFT': 'lacasaWFT.sale.order',
    'MrMix': 'MrMix.sale.order',
}

PAYMENT_METHOD_SELECTION = [
    ('bea', 'BEA'),
    ('payme', 'Payme'),
    ('credit_card', 'Credit Card'),
    ('hsbc', 'HSBC'),
    ('paypal', 'Paypal'),
    ('internal_transfer', 'Internal Transfer'),
    ('monthly', 'Monthly'),
]

CALL_VAN_SELECTION = [
    ('ah_yuen', '阿源'),
    ('no_need', 'No need'),
    ('event_team', 'Arranged by event team'),
    ('man_zai', '文仔'),
    ('lalamove', 'Lalamove'),
    ('hang_gor', '恆哥'),
    ('self_deliver', '自己送'),
    ('roy', 'Roy'),
    ('lik_pak', '力柏'),
    ('self_pickup', 'Self Pick-up'),
    ('dat', '達'),
    ('fu_gor', '虎哥'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # Catering fields (from CRM)
    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    client_type = fields.Selection(CLIENT_TYPE_SELECTION, string='Client Type')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    no_logo = fields.Boolean(
        string='No Logo',
        help='Hide LaCasa branding from packaging / signage (white-label).',
    )
    setup_type = fields.Selection(
        SETUP_TYPE_SELECTION, string='Setup Type',
        help='Distinguishes equipment-only / simple-setup orders from full event service.',
    )
    is_wedding = fields.Boolean(
        string='Wedding-related',
        help='Tick if this food tasting is for a wedding.',
    )
    so_prefix_preview = fields.Char(
        string='Sequence Prefix',
        compute='_compute_so_prefix_preview',
        help='Preview of the SO sequence prefix that will be used at creation '
             '(based on brand + service type + flags). Locked once the order is saved.',
    )
    hide_prices_on_quote = fields.Boolean(
        string='Hide Prices on Quotation',
        help='When ticked, the printed quotation hides per-line prices and totals '
             '(useful for sending a menu preview before pricing is finalised).',
    )

    # SO-specific fields
    payment_method = fields.Selection(
        PAYMENT_METHOD_SELECTION, string='Payment Method',
    )
    attention_to_id = fields.Many2one(
        'res.partner',
        string='Attention To',
        help='Contact person for this order',
    )
    call_van = fields.Selection(CALL_VAN_SELECTION, string='Call Van')
    delivery_time = fields.Float(string='Event / Delivery Time')
    event_hour = fields.Float(
        string='Event Hour',
        help='Duration of the event, in hours.',
    )

    @api.model
    def _resolve_seq_prefix(self, brand, service_format, service_type,
                            setup_type, no_logo, is_wedding):
        """Resolve the SO sequence prefix from order attributes.

        Returns one of the keys of SO_SEQUENCE_PREFIX_MAP, or None if no
        catering-specific prefix applies (caller falls back to default
        sale.order sequence).
        """
        if brand == 'mr_mix':
            return 'MrMix'
        if brand != 'lacasa':
            return None

        if service_type in ('wedding_buffet', 'wedding_cocktail'):
            return 'lacasaW'
        if service_type == 'food_tasting':
            return 'lacasaWFT' if is_wedding else 'lacasaFT'
        if setup_type in ('equipment_only', 'simple_setup'):
            return 'lacasaK'
        if service_format == 'event_catering':
            return 'lacasaE_N_' if no_logo else 'lacasaE'
        if service_format == 'food_delivery':
            return 'lacasaN' if no_logo else 'lacasa'
        return None

    @api.depends('brand', 'service_format', 'service_type',
                 'setup_type', 'no_logo', 'is_wedding')
    def _compute_so_prefix_preview(self):
        for order in self:
            prefix = self._resolve_seq_prefix(
                order.brand, order.service_format, order.service_type,
                order.setup_type, order.no_logo, order.is_wedding,
            )
            order.so_prefix_preview = prefix or _('(default)')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Skip if user already set a non-default name
            current_name = vals.get('name')
            if current_name and current_name != _('New'):
                continue
            prefix = self._resolve_seq_prefix(
                vals.get('brand'),
                vals.get('service_format'),
                vals.get('service_type'),
                vals.get('setup_type'),
                vals.get('no_logo'),
                vals.get('is_wedding'),
            )
            if not prefix:
                continue
            seq_code = SO_SEQUENCE_PREFIX_MAP[prefix]
            seq_value = self.env['ir.sequence'].next_by_code(seq_code)
            if seq_value:
                vals['name'] = seq_value
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'call_van' in vals and not self.env.context.get('skip_call_van_sync'):
            for so in self:
                invs = so.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.call_van != vals['call_van'])
                if invs:
                    invs.with_context(skip_call_van_sync=True).write({'call_van': vals['call_van']})
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id_attention(self):
        """Default attention_to_id based on partner type."""
        if self.partner_id:
            if not self.partner_id.is_company:
                # Individual contact — default to themselves
                self.attention_to_id = self.partner_id
            else:
                self.attention_to_id = False

    def _prepare_invoice(self):
        """Pass catering fields to the invoice."""
        vals = super()._prepare_invoice()
        vals.update({
            'brand': self.brand,
            'attention_to_id': self.attention_to_id.id if self.attention_to_id else False,
            'call_van': self.call_van,
            'delivery_time': self.delivery_time,
            'event_hour': self.event_hour,
            'event_date': self.commitment_date,
            'event_street': self.partner_shipping_id.street if self.partner_shipping_id else False,
            'event_street2': self.partner_shipping_id.street2 if self.partner_shipping_id else False,
            'service_format': self.service_format,
            'service_type': self.service_type,
            'delivery_type': self.delivery_type,
            'guest_count': self.guest_count,
            'event_remark': self.event_remark,
            'payment_method': self.payment_method,
            'no_logo': self.no_logo,
            'setup_type': self.setup_type,
            'is_wedding': self.is_wedding,
        })
        return vals


class SaleOrderFromCRM(models.Model):
    _inherit = 'crm.lead'

    def _prepare_opportunity_quotation_context(self):
        """Pass catering fields when creating quotation from opportunity."""
        ctx = super()._prepare_opportunity_quotation_context()
        ctx.update({
            'default_brand': self.brand,
            'default_client_type': self.client_type,
            'default_service_format': self.service_format,
            'default_service_type': self.service_type,
            'default_delivery_type': self.delivery_type,
            'default_guest_count': self.guest_count,
            'default_event_remark': self.event_remark,
            'default_commitment_date': self.event_date,
            'default_delivery_time': self.delivery_time,
            'default_event_hour': self.event_hour,
            'default_no_logo': self.no_logo,
            'default_setup_type': self.setup_type,
            'default_is_wedding': self.is_wedding,
        })
        # Build delivery address
        if self.event_street:
            address_parts = [self.event_street]
            if self.event_street2:
                address_parts.append(self.event_street2)
            ctx['default_note'] = ctx.get('default_note', '') or ''
        return ctx
