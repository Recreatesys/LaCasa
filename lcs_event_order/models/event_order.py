from odoo import api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
)
from odoo.addons.lcs_crm_catering.models.sale_order import CALL_VAN_SELECTION

PAYMENT_STATUS_SELECTION = [
    ('unpaid', 'Unpaid'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled'),
]


class EventOrder(models.Model):
    _name = 'lcs.event.order'
    _description = 'Event Order'
    _order = 'event_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='EO Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='sale_order_id.partner_id',
        store=True,
    )

    # Catering fields
    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    event_date = fields.Date(string='Event / Delivery Date')
    event_street = fields.Char(string='Street')
    event_street2 = fields.Char(string='Street 2')
    event_country_id = fields.Many2one('res.country', string='Country')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    delivery_time = fields.Float(string='Delivery Time')
    call_van = fields.Selection(
        CALL_VAN_SELECTION,
        string='Call Van',
        related='sale_order_id.call_van',
        store=True,
        readonly=False,
    )

    # EO Lines (kitchen product lines)
    line_ids = fields.One2many(
        'lcs.event.order.line', 'order_id', string='Order Lines',
    )

    # Payment status (computed from SO invoices)
    payment_status = fields.Selection(
        PAYMENT_STATUS_SELECTION,
        string='Payment Status',
        compute='_compute_payment_status',
        store=True,
        tracking=True,
    )

    # Versioning & change tracking
    version = fields.Integer(string='Version', default=1, readonly=True)
    last_change_date = fields.Datetime(
        string='Last Change Date', readonly=True,
    )
    change_summary = fields.Text(
        string='Change Summary', readonly=True,
    )
    change_acknowledged = fields.Boolean(
        string='Acknowledged', default=False,
    )
    acknowledged_by = fields.Many2one(
        'res.users', string='Acknowledged By', readonly=True,
    )
    acknowledged_date = fields.Datetime(
        string='Acknowledged Date', readonly=True,
    )

    # Display helpers
    has_unacknowledged_change = fields.Boolean(
        compute='_compute_has_unacknowledged_change',
        store=True,
    )

    @api.depends(
        'sale_order_id.state',
        'sale_order_id.invoice_ids',
        'sale_order_id.invoice_ids.state',
        'sale_order_id.invoice_ids.payment_state',
    )
    def _compute_payment_status(self):
        for eo in self:
            so = eo.sale_order_id
            if so.state == 'cancel':
                eo.payment_status = 'cancelled'
                continue

            invoices = so.invoice_ids.filtered(
                lambda inv: inv.state == 'posted'
                and inv.move_type == 'out_invoice'
            )
            if not invoices:
                eo.payment_status = 'unpaid'
                continue

            payment_states = invoices.mapped('payment_state')
            if any(ps in ('paid', 'in_payment', 'partial') for ps in payment_states):
                eo.payment_status = 'paid'
            else:
                eo.payment_status = 'unpaid'

    @api.depends('version', 'change_acknowledged')
    def _compute_has_unacknowledged_change(self):
        for eo in self:
            eo.has_unacknowledged_change = (
                eo.version > 1 and not eo.change_acknowledged
            )

    def action_acknowledge_change(self):
        """Mark the change as acknowledged by the current user."""
        self.ensure_one()
        self.write({
            'change_acknowledged': True,
            'acknowledged_by': self.env.uid,
            'acknowledged_date': fields.Datetime.now(),
        })

    def _update_from_sale_order(self, so, changes_desc=None):
        """Update EO fields from the confirmed SO, bump version."""
        vals = self._prepare_eo_vals_from_so(so)
        vals.update({
            'version': self.version + 1,
            'last_change_date': fields.Datetime.now(),
            'change_summary': changes_desc or 'Sales Order updated',
            'change_acknowledged': False,
            'acknowledged_by': False,
            'acknowledged_date': False,
        })

        # Update lines
        self.line_ids.unlink()
        line_vals = self._prepare_eo_lines_from_so(so)
        vals['line_ids'] = [(0, 0, lv) for lv in line_vals]

        self.write(vals)

    @api.model
    def _prepare_eo_vals_from_so(self, so):
        """Prepare EO field values from a sales order."""
        return {
            'brand': so.brand,
            'event_date': so.commitment_date.date() if so.commitment_date else False,
            'event_street': so.partner_shipping_id.street if so.partner_shipping_id else '',
            'event_street2': so.partner_shipping_id.street2 if so.partner_shipping_id else '',
            'event_country_id': (
                so.partner_shipping_id.country_id.id
                if so.partner_shipping_id and so.partner_shipping_id.country_id
                else False
            ),
            'service_format': so.service_format,
            'service_type': so.service_type,
            'delivery_type': so.delivery_type,
            'guest_count': so.guest_count,
            'event_remark': so.event_remark,
            'delivery_time': so.delivery_time,
        }

    @api.model
    def _prepare_eo_lines_from_so(self, so):
        """Prepare EO line values from SO lines.

        If the SO line has eo_qty/eo_unit from a catering set, use those.
        Otherwise fall back to product-level kitchen_ratio.
        Only include lines that are selected (dish_selected) or non-set lines.
        """
        lines = []
        for sol in so.order_line.filtered(lambda l: not l.display_type):
            # Skip unselected set lines
            if hasattr(sol, 'is_set_line') and sol.is_set_line and not sol.dish_selected:
                continue

            product = sol.product_id

            # Use set-level EO qty/unit if available
            if hasattr(sol, 'eo_qty') and sol.eo_qty:
                kitchen_qty = sol.eo_qty
                kitchen_uom = sol.eo_unit or ''
            else:
                kitchen_ratio = product.kitchen_ratio or 1.0
                kitchen_qty = sol.product_uom_qty / kitchen_ratio if kitchen_ratio else sol.product_uom_qty
                kitchen_uom = product.kitchen_uom or product.uom_id.name

            lines.append({
                'product_id': product.id,
                'description': sol.name,
                'so_qty': sol.product_uom_qty,
                'kitchen_qty': kitchen_qty,
                'kitchen_uom': kitchen_uom,
            })
        return lines
