from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Header field changes that should propagate to the EO.
EO_SYNC_HEADER_FIELDS = frozenset({
    'commitment_date', 'guest_count', 'partner_shipping_id',
    'delivery_type', 'service_type', 'service_format', 'brand',
    'event_remark', 'delivery_time', 'event_hour',
})

# SO-line field changes that should propagate to the EO.
EO_SYNC_LINE_FIELDS = frozenset({
    'product_id', 'product_uom_qty', 'name', 'dish_selected',
    'display_type',
})


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    event_order_ids = fields.One2many(
        'lcs.event.order', 'sale_order_id', string='Event Orders',
    )
    event_order_count = fields.Integer(
        compute='_compute_event_order_count',
    )

    def _compute_event_order_count(self):
        for so in self:
            so.event_order_count = len(so.event_order_ids)

    def action_confirm(self):
        """Override to create or update Event Order on SO confirmation."""
        res = super().action_confirm()
        for so in self.with_context(skip_eo_sync=True):
            existing_eo = so.event_order_ids
            if existing_eo:
                changes = so._detect_eo_changes(existing_eo[0])
                existing_eo[0]._update_from_sale_order(so, changes)
            else:
                so._create_event_order()
        return res

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_eo_sync'):
            return res
        if EO_SYNC_HEADER_FIELDS.isdisjoint(vals):
            return res
        for so in self:
            if so.state == 'sale' and so.event_order_ids:
                so._sync_to_event_order()
        return res

    def _create_event_order(self):
        """Create one Event Order per confirmed Sales Order."""
        self.ensure_one()
        EO = self.env['lcs.event.order']
        vals = EO._prepare_eo_vals_from_so(self, day_offset=0)
        vals.update({
            'sale_order_id': self.id,
            'name': '%s-v1' % self.name,
            'version': 1,
        })
        line_vals = EO._prepare_eo_lines_from_so(self, day_offset=0)
        vals['line_ids'] = [(0, 0, lv) for lv in line_vals]
        return EO.create(vals)

    def _sync_to_event_order(self):
        """Push current SO state to each linked EO (header + lines, bump version).

        Post-Phase-1: 1 SO = 1 EO. Ensure exactly one EO exists, then push
        the diff.
        """
        self.ensure_one()
        if not self.event_order_ids:
            self._create_event_order()
        for eo in self.event_order_ids:
            changes = self._detect_eo_changes(eo)
            eo._update_from_sale_order(self, changes)

    def action_update_event_order(self):
        """Manual sync trigger from the SO form."""
        self.ensure_one()
        if not self.event_order_ids:
            raise UserError(_("No Event Order is linked to this Sales Order yet."))
        self._sync_to_event_order()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Event Order Updated'),
                'message': _('Version bumped to v%d') % self.event_order_ids[0].version,
                'type': 'success',
                'sticky': False,
            },
        }

    def _detect_eo_changes(self, eo):
        """Summarize what changed between current SO and existing EO."""
        changes = []
        if self.commitment_date:
            new_date = self.commitment_date.date()
            if eo.event_date != new_date:
                changes.append('Delivery date: %s → %s' % (eo.event_date or '—', new_date))
        if self.guest_count != eo.guest_count:
            changes.append('Guest count: %s → %s' % (eo.guest_count, self.guest_count))

        # Compare lines via sale_line_id where available
        existing_sol_ids = set(eo.line_ids.mapped('sale_line_id').ids)
        new_so_lines = self.order_line.filtered(
            lambda l: not l.display_type
            and not (getattr(l, 'is_set_line', False) and not getattr(l, 'dish_selected', False))
        )
        new_sol_ids = set(new_so_lines.ids)

        added = new_sol_ids - existing_sol_ids
        removed = existing_sol_ids - new_sol_ids
        if added:
            changes.append('+%d line(s) added' % len(added))
        if removed:
            changes.append('-%d line(s) removed' % len(removed))

        qty_changes = 0
        for line in eo.line_ids:
            sol = line.sale_line_id
            if sol and sol.id in new_sol_ids and sol.product_uom_qty != line.so_qty:
                qty_changes += 1
        if qty_changes:
            changes.append('%d line qty change(s)' % qty_changes)

        return '; '.join(changes) if changes else 'Sales Order updated'

    def action_view_event_orders(self):
        """Open Event Orders linked to this SO."""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Event Orders'),
            'res_model': 'lcs.event.order',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }
        if self.event_order_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.event_order_ids[0].id
        return action


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _trigger_eo_sync(self, orders):
        """Sync each confirmed order that has at least one EO."""
        if self.env.context.get('skip_eo_sync'):
            return
        for so in orders.filtered(lambda o: o.state == 'sale' and o.event_order_ids):
            so._sync_to_event_order()

    def write(self, vals):
        res = super().write(vals)
        if not EO_SYNC_LINE_FIELDS.isdisjoint(vals):
            self._trigger_eo_sync(self.mapped('order_id'))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._trigger_eo_sync(lines.mapped('order_id'))
        return lines

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        self._trigger_eo_sync(orders)
        return res
