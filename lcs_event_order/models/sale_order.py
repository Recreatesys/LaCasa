from odoo import fields, models, _


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
        for so in self:
            existing_eo = so.event_order_ids
            if existing_eo:
                # SO re-confirmed after modification — update EO, bump version
                changes = so._detect_eo_changes(existing_eo[0])
                existing_eo[0]._update_from_sale_order(so, changes)
            else:
                # First confirmation — create EO
                so._create_event_order()
        return res

    def _create_event_order(self):
        """Create an Event Order from the confirmed Sales Order."""
        self.ensure_one()
        EO = self.env['lcs.event.order']
        vals = EO._prepare_eo_vals_from_so(self)
        vals.update({
            'sale_order_id': self.id,
            'name': '%s-v1' % self.name,
            'version': 1,
        })
        # Prepare lines
        line_vals = EO._prepare_eo_lines_from_so(self)
        vals['line_ids'] = [(0, 0, lv) for lv in line_vals]
        return EO.create(vals)

    def _detect_eo_changes(self, eo):
        """Detect what changed between current SO and existing EO."""
        changes = []
        if self.commitment_date:
            new_date = self.commitment_date.date()
            if eo.event_date and new_date != eo.event_date:
                changes.append(
                    'Delivery date: %s → %s' % (eo.event_date, new_date)
                )
        if self.guest_count != eo.guest_count:
            changes.append(
                'Guest count: %s → %s' % (eo.guest_count, self.guest_count)
            )
        # Compare line counts
        old_count = len(eo.line_ids)
        new_count = len(self.order_line.filtered(lambda l: not l.display_type))
        if old_count != new_count:
            changes.append(
                'Product lines: %d → %d' % (old_count, new_count)
            )
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
