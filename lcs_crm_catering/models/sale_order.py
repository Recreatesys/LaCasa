from odoo import api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    CLIENT_TYPE_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
)

PAYMENT_METHOD_SELECTION = [
    ('bea', 'BEA'),
    ('payme', 'Payme'),
    ('credit_card', 'Credit Card'),
    ('hsbc', 'HSBC'),
    ('paypal', 'Paypal'),
    ('internal_transfer', 'Internal Transfer'),
    ('monthly', 'Monthly'),
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

    # SO-specific fields
    payment_method = fields.Selection(
        PAYMENT_METHOD_SELECTION, string='Payment Method',
    )
    attention_to_id = fields.Many2one(
        'res.partner',
        string='Attention To',
        help='Contact person for this order',
    )
    call_van = fields.Char(string='Call Van')
    delivery_time = fields.Float(string='Delivery Time')

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
            'service_format': self.service_format,
            'service_type': self.service_type,
            'delivery_type': self.delivery_type,
            'guest_count': self.guest_count,
            'event_remark': self.event_remark,
            'payment_method': self.payment_method,
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
        })
        # Build delivery address
        if self.event_street:
            address_parts = [self.event_street]
            if self.event_street2:
                address_parts.append(self.event_street2)
            ctx['default_note'] = ctx.get('default_note', '') or ''
        return ctx
