from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_set_line = fields.Boolean(
        string='Set Dish Line', default=False,
        help='This line was generated from a catering set expansion',
    )
    dish_selected = fields.Boolean(
        string='Selected', default=False,
        help='Tick to include this dish in the order',
    )
    set_product_id = fields.Many2one(
        'product.product', string='From Set',
        help='The set product this dish belongs to',
    )
    catering_set_id = fields.Many2one(
        'lcs.catering.set', string='Catering Set',
    )

    @api.onchange('product_id')
    def _onchange_product_id_expand_set(self):
        """When a set product is added, expand into dish lines."""
        if not self.product_id:
            return
        catering_set = self.env['lcs.catering.set'].search([
            ('product_id.product_variant_ids', 'in', [self.product_id.id]),
        ], limit=1)
        if not catering_set:
            return

        # Return action to trigger set expansion
        return {
            'warning': {
                'title': _('Catering Set'),
                'message': _(
                    'This is a set menu "%s". Click "Expand Set" button '
                    'to generate dish lines.'
                ) % catering_set.name,
            }
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_expand_sets(self):
        """Expand all set products in the SO into individual dish lines."""
        self.ensure_one()
        lines_to_process = self.order_line.filtered(
            lambda l: not l.display_type and not l.is_set_line
        )

        for line in lines_to_process:
            catering_set = self.env['lcs.catering.set'].search([
                ('product_id.product_variant_ids', 'in', [line.product_id.id]),
            ], limit=1)
            if not catering_set:
                continue

            # Check if already expanded
            existing = self.order_line.filtered(
                lambda l: l.set_product_id == line.product_id
                and l.is_set_line
            )
            if existing:
                continue

            # Create section header
            self.env['sale.order.line'].create({
                'order_id': self.id,
                'display_type': 'line_section',
                'name': '── %s ──' % catering_set.name,
                'sequence': line.sequence + 1,
            })

            # Create dish lines from set
            seq = line.sequence + 2
            for set_line in catering_set.line_ids:
                product_variant = set_line.product_id
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'product_id': product_variant.id,
                    'name': set_line.description or product_variant.display_name,
                    'product_uom_qty': 0,  # 0 until selected
                    'price_unit': set_line.unit_price,
                    'is_set_line': True,
                    'dish_selected': False,
                    'set_product_id': line.product_id.id,
                    'catering_set_id': catering_set.id,
                    'sequence': seq,
                })
                seq += 1

            # Set the original set line qty to 0 (it's just a container)
            line.write({'product_uom_qty': 1, 'price_unit': 0})

    def _get_selected_dish_count(self, catering_set_id, category_id):
        """Count how many dishes are selected for a set+category."""
        return len(self.order_line.filtered(
            lambda l: l.is_set_line
            and l.catering_set_id.id == catering_set_id
            and l.dish_selected
            and l.product_id.categ_id.id == category_id
        ))
