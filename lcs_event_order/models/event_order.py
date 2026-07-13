from odoo import api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
)
from odoo.addons.lcs_crm_catering.models.sale_order import CALL_VAN_SELECTION

# Selection keys are legacy ("paid"/"unpaid") for DB compatibility, but the
# user-facing labels and compute logic now reflect SO confirmation status,
# not invoice payment.
PAYMENT_STATUS_SELECTION = [
    ('unpaid', 'Unconfirm'),
    ('paid', 'Order Confirm'),
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
    # Multi-day support: which day of the SO event range this EO covers (0-based)
    event_day_offset = fields.Integer(
        string='Event Day (0-based)',
        default=0, readonly=True,
        help='0 = Day 1, 1 = Day 2, etc. Used when the SO spans multiple days.',
    )
    event_date = fields.Date(string='Event / Delivery Date')
    event_street = fields.Char(string='Street')
    event_street2 = fields.Char(string='Street 2')
    event_country_id = fields.Many2one('res.country', string='Country')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    delivery_time = fields.Float(string='Event / Delivery Time')
    event_hour = fields.Float(
        string='Event Hour',
        help='Duration of the event, in hours.',
    )
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

    # Order status (computed from SO state).
    # Field name kept as `payment_status` for backwards-compat; semantics
    # now reflect SO confirmation, not invoice payment.
    payment_status = fields.Selection(
        PAYMENT_STATUS_SELECTION,
        string='Order Status',
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

    # Linked Delivery Orders (stock.pickings for this event day)
    picking_ids = fields.Many2many(
        'stock.picking', string='Delivery Orders',
        compute='_compute_picking_ids',
    )
    picking_count = fields.Integer(
        string='# Delivery Orders', compute='_compute_picking_ids',
    )

    @api.depends('sale_order_id.name', 'event_day_offset')
    def _compute_picking_ids(self):
        Picking = self.env.get('stock.picking')
        for eo in self:
            if Picking is None or not eo.sale_order_id:
                eo.picking_ids = False
                eo.picking_count = 0
                continue
            pg_name = '%s-D%d' % (
                eo.sale_order_id.name, (eo.event_day_offset or 0) + 1,
            )
            pickings = Picking.search([
                ('group_id.name', '=', pg_name),
            ])
            eo.picking_ids = pickings
            eo.picking_count = len(pickings)

    def action_view_pickings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Delivery Orders',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.picking_ids.ids)],
        }

    # Chef sign-off
    chef_signoff_user_id = fields.Many2one(
        'res.users', string='Chef Sign-off', readonly=True, tracking=True,
    )
    chef_signoff_date = fields.Datetime(
        string='Sign-off Date', readonly=True, tracking=True,
    )
    is_chef_signed_off = fields.Boolean(
        string='Chef Signed Off',
        compute='_compute_is_chef_signed_off', store=True,
    )

    @api.depends('chef_signoff_user_id')
    def _compute_is_chef_signed_off(self):
        for eo in self:
            eo.is_chef_signed_off = bool(eo.chef_signoff_user_id)

    def action_chef_signoff(self):
        """Record chef sign-off for this EO."""
        for eo in self:
            eo.write({
                'chef_signoff_user_id': self.env.uid,
                'chef_signoff_date': fields.Datetime.now(),
            })

    def action_chef_unsignoff(self):
        """Clear chef sign-off (e.g. EO needs to be revised)."""
        for eo in self:
            eo.write({
                'chef_signoff_user_id': False,
                'chef_signoff_date': False,
            })

    def action_cancel_sale_order(self):
        """Cancel the linked Sales Order. The EO Order Status will then
        auto-flip to 'Cancelled' via _compute_payment_status (which reads
        sale_order_id.state)."""
        for eo in self:
            so = eo.sale_order_id
            if so and so.state != 'cancel':
                so._action_cancel()
        return True

    @api.depends('sale_order_id.state')
    def _compute_payment_status(self):
        """Order Status reflects the underlying SO's confirmation state.

        - SO confirmed (state in sale/done) → "Order Confirm" (key 'paid')
        - SO cancelled → "Cancelled"
        - SO draft/sent → "Unconfirm" (key 'unpaid')
        """
        for eo in self:
            state = eo.sale_order_id.state
            if state == 'cancel':
                eo.payment_status = 'cancelled'
            elif state in ('sale', 'done'):
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
        """Update EO from SO via diff/merge and bump version.

        Header fields refresh from SO. Lines are matched by `sale_line_id`:
        existing matches get SO-derived fields refreshed; new SO lines become
        new EO lines; EO lines whose source SO line vanished get unlinked.
        Kitchen-only fields (`kitchen_qty`, `note`) are preserved.
        """
        self.ensure_one()

        # Header refresh + version bump. Preserve this EO's own day offset.
        vals = self._prepare_eo_vals_from_so(so, day_offset=self.event_day_offset or 0)
        vals.update({
            'version': self.version + 1,
            'last_change_date': fields.Datetime.now(),
            'change_summary': changes_desc or 'Sales Order updated',
            'change_acknowledged': False,
            'acknowledged_by': False,
            'acknowledged_date': False,
        })
        self.with_context(skip_eo_sync=True).write(vals)

        # Diff/merge lines
        self._sync_lines_from_so(so)

    def _sync_lines_from_so(self, so):
        """Diff/merge EO lines against current SO line scope."""
        self.ensure_one()
        EOLine = self.env['lcs.event.order.line']

        # Desired state from SO (each entry carries sale_line_id)
        desired = self._prepare_eo_lines_from_so(so, day_offset=self.event_day_offset or 0)
        desired_by_sol = {d['sale_line_id']: d for d in desired if d.get('sale_line_id')}

        existing_by_sol = {l.sale_line_id.id: l for l in self.line_ids if l.sale_line_id}

        # Update / create
        for sol_id, lv in desired_by_sol.items():
            if sol_id in existing_by_sol:
                line = existing_by_sol[sol_id]
                # Refresh SO-derived fields; preserve kitchen_qty & note
                line.write({
                    'product_id': lv['product_id'],
                    'description': lv['description'],
                    'so_qty': lv['so_qty'],
                    'kitchen_uom': lv['kitchen_uom'],
                })
            else:
                EOLine.create(dict(lv, order_id=self.id))

        # Remove EO lines whose source SO line no longer in scope
        # (Legacy lines without sale_line_id are left untouched.)
        for sol_id, line in existing_by_sol.items():
            if sol_id not in desired_by_sol:
                line.unlink()

    @api.model
    def _prepare_eo_vals_from_so(self, so, day_offset=0):
        """Prepare EO field values from a sales order for a given day offset.

        The EO's event_date is computed as SO.event_date_start + day_offset,
        falling back to commitment_date.date() for single-day / legacy SOs.
        """
        from datetime import timedelta
        # Prefer the new range fields; fall back to legacy commitment_date.
        base_date = so.event_date_start or (
            so.commitment_date.date() if so.commitment_date else False
        )
        event_date = (
            base_date + timedelta(days=day_offset)
            if base_date else False
        )
        return {
            'brand': so.brand,
            'event_date': event_date,
            'event_day_offset': day_offset,
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
            'event_hour': so.event_hour,
        }

    @api.model
    def _prepare_eo_lines_from_so(self, so, day_offset=0):
        """Prepare EO line values for the SO lines matching this day_offset.

        For single-day (or legacy) SOs, day_offset=0 catches all lines that
        default to offset 0. For multi-day SOs, each EO gets only the SO
        lines whose event_day_offset matches its own day.
        """
        lines = []
        for sol in so.order_line.filtered(lambda l: not l.display_type):
            # Filter by day
            sol_offset = int(getattr(sol, 'event_day_offset', 0) or 0)
            if sol_offset != day_offset:
                continue

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
                'sale_line_id': sol.id,
                'description': sol.name,
                'so_qty': sol.product_uom_qty,
                'kitchen_qty': kitchen_qty,
                'kitchen_uom': kitchen_uom,
            })
        return lines
