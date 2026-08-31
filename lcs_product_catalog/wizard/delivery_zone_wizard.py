"""Locate the delivery zone for a quotation and add the delivery charge.

C08 (client comment, slide 8): "Possible to map the delivery charge directly
by tracking Event address & delivery type?"

Two steps, deliberately separated so a failed lookup never blocks a quotation:

  1. Look up  — send the address to Google, match the district it returns
                against lcs.delivery.district, show the resulting zone, the
                product and the price.
  2. Confirm  — add (or replace) the delivery line on the Sales Order.

Whatever step 1 does, the district stays editable. Real LCS addresses include
things like "Self pickup" and "中環交易廣場1期 地下交收", which no geocoder will
resolve, so choosing the district by hand is a first-class path rather than an
error case.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DeliveryZoneWizard(models.TransientModel):
    _name = 'lcs.delivery.zone.wizard'
    _description = 'Locate Delivery Zone'

    order_id = fields.Many2one(
        'sale.order', string='Quotation', required=True, ondelete='cascade',
    )
    address = fields.Text(
        string='Delivery Address', required=True,
        help='Pre-filled from the event address, falling back to the '
             'customer\'s delivery address.',
    )
    delivery_type = fields.Selection(
        related='order_id.delivery_type', string='Delivery Type', readonly=True,
    )

    state = fields.Selection(
        [('input', 'Address'), ('result', 'Result')],
        default='input', readonly=True,
    )
    lookup_message = fields.Text(string='Lookup Result', readonly=True)
    lookup_failed = fields.Boolean(readonly=True)
    formatted_address = fields.Char(string='Google Match', readonly=True)
    latitude = fields.Float(digits=(10, 7), readonly=True)
    longitude = fields.Float(digits=(10, 7), readonly=True)

    district_id = fields.Many2one(
        'lcs.delivery.district', string='District / Locality',
        help='Filled in by the Google lookup. Always editable — override it '
             'when the address is unusual or the lookup could not resolve it.',
    )
    zone_id = fields.Many2one(
        'lcs.delivery.zone', string='Delivery Zone',
        compute='_compute_zone', store=True, readonly=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Delivery Charge',
        compute='_compute_product', store=True, readonly=True,
    )
    price = fields.Float(
        related='product_id.lst_price', string='Price', readonly=True,
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id', readonly=True,
    )
    no_rate_reason = fields.Char(compute='_compute_product', readonly=True)

    # ── defaults ──

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        order = self.env['sale.order'].browse(
            self.env.context.get('active_id')
        ).exists()
        if order:
            vals['order_id'] = order.id
            vals.setdefault('address', order._lcs_delivery_address_text())
        return vals

    # ── computes ──

    @api.depends('district_id')
    def _compute_zone(self):
        for wiz in self:
            wiz.zone_id = wiz.district_id.zone_id

    @api.depends('zone_id', 'delivery_type')
    def _compute_product(self):
        for wiz in self:
            product = reason = False
            if wiz.zone_id and wiz.delivery_type:
                product = wiz.zone_id._get_rate_product(wiz.delivery_type)
                if not product:
                    label = dict(
                        wiz._fields['delivery_type'].selection
                    ).get(wiz.delivery_type, wiz.delivery_type)
                    reason = _(
                        'No delivery rate is configured for %(zone)s with '
                        '"%(type)s". LCS has not supplied that rate yet — add '
                        'it under Sales ▸ Configuration ▸ Delivery Zones, or '
                        'enter the charge on the quotation by hand.',
                        zone=wiz.zone_id.name, type=label,
                    )
            elif wiz.zone_id and not wiz.delivery_type:
                reason = _('Set a Delivery Type on the quotation first.')
            wiz.product_id = product
            wiz.no_rate_reason = reason

    # ── actions ──

    def action_lookup(self):
        """Ask Google where this address is, then match it to a district."""
        self.ensure_one()
        result = self.env['lcs.google.geocoder'].geocode(self.address)

        if not result.get('ok'):
            self.write({
                'state': 'result',
                'lookup_failed': True,
                'lookup_message': result.get('error'),
                'formatted_address': False,
            })
            return self._reopen()

        district = self.env['lcs.delivery.district']._match_address_parts(
            result['parts']
        )
        vals = {
            'state': 'result',
            'formatted_address': result['formatted'],
            'latitude': result.get('lat') or 0.0,
            'longitude': result.get('lng') or 0.0,
            'lookup_failed': not district,
        }
        if district:
            vals['district_id'] = district.id
            vals['lookup_message'] = _(
                'Matched "%(district)s" → %(zone)s.',
                district=district.name, zone=district.zone_id.name,
            )
        else:
            vals['lookup_message'] = _(
                'Google found the address but it did not match any configured '
                'district. Choose the district below by hand.'
            )
        self.write(vals)
        return self._reopen()

    def action_confirm(self):
        """Put the delivery charge on the quotation."""
        self.ensure_one()
        if not self.product_id:
            raise UserError(
                self.no_rate_reason
                or _('Choose a district so a delivery charge can be found.')
            )
        order = self.order_id
        if order.state not in ('draft', 'sent'):
            raise UserError(_(
                'This quotation is no longer a draft, so its delivery charge '
                'cannot be changed here.'
            ))

        order._lcs_apply_delivery_charge(
            self.product_id, self.zone_id, self.district_id,
            address=self.formatted_address or self.address,
        )
        return {'type': 'ir.actions.act_window_close'}

    def _reopen(self):
        """Keep the dialog open on the same record after a lookup."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
