from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.lcs_product_catalog.models.catering_set import SIZE_LABELS


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
    set_unit = fields.Char(string='Set Unit', help='Customer-facing unit from set config')
    eo_qty = fields.Float(string='EO Qty', digits='Product Unit of Measure')
    eo_unit = fields.Char(string='EO Unit', help='Kitchen-facing unit from set config')
    set_line_code = fields.Char(string='Code', help='Dish code within the set')
    is_addon_piece = fields.Boolean(
        string='Add-on (per piece)', default=False,
        help='This line is an extra per-piece add-on',
    )
    per_piece_price = fields.Float(
        string='Per Piece Price',
        help='Price per piece for add-on ordering',
    )
    full_price = fields.Float(
        string='Full Price',
        help='Stored full price — applied when dish is selected, zeroed when not',
    )

    @api.onchange('dish_selected')
    def _onchange_dish_selected(self):
        """Set price to full_price when selected, 0 when not."""
        if self.is_set_line:
            if self.dish_selected:
                self.price_unit = self.full_price
            else:
                self.price_unit = 0

    @api.onchange('product_id')
    def _onchange_product_id_expand_set(self):
        """When a set product is added, show a hint."""
        if not self.product_id:
            return
        catering_set = self.env['lcs.catering.set'].search([
            ('product_id.product_variant_ids', 'in', [self.product_id.id]),
        ], limit=1)
        if not catering_set:
            return
        return {
            'warning': {
                'title': _('Catering Set'),
                'message': _(
                    'This is a set menu "%s". Click "Expand Sets" button '
                    'to generate dish lines.\n\n%s'
                ) % (catering_set.name, catering_set.recommendation or ''),
            }
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_reload_sets(self):
        """Remove all existing set lines and re-expand with current guest count."""
        self.ensure_one()
        # Remember which dishes were selected
        selected = {}
        for line in self.order_line.filtered(lambda l: l.is_set_line and l.dish_selected):
            key = (line.set_product_id.id, line.product_id.id, line.is_addon_piece)
            selected[key] = line.product_uom_qty

        # Remove all set-generated lines (set lines + section/note headers)
        set_lines = self.order_line.filtered(
            lambda l: l.is_set_line
            or (l.display_type and l.set_product_id)
        )
        # Also remove section/note lines created by expansion
        # These don't have set_product_id, so find them by sequence proximity
        all_set_product_ids = self.order_line.filtered(
            lambda l: l.is_set_line
        ).mapped('set_product_id')

        lines_to_remove = self.order_line.filtered(lambda l: l.is_set_line)
        # Also remove display_type lines that were created for sets
        for line in self.order_line.filtered(lambda l: l.display_type):
            # Check if this is a set section/note by name patterns
            if line.name and ('──' in line.name or '↳' in line.name or line.name.startswith('💡')):
                lines_to_remove |= line
            # Check if it's a section that matches a set section name
            if line.display_type == 'line_section':
                for set_line in self.order_line.filtered(lambda l: l.is_set_line):
                    if set_line.catering_set_id:
                        sections = set_line.catering_set_id.line_ids.mapped('section')
                        if line.name in sections:
                            lines_to_remove |= line
                            break

        lines_to_remove.unlink()

        # Re-expand
        self.action_expand_sets()

        # Restore selections
        for line in self.order_line.filtered(lambda l: l.is_set_line):
            key = (line.set_product_id.id, line.product_id.id, line.is_addon_piece)
            if key in selected:
                line.write({
                    'dish_selected': True,
                    'price_unit': line.full_price,
                    'product_uom_qty': selected[key] if line.is_addon_piece else line.product_uom_qty,
                })

    def action_expand_sets(self):
        """Expand all set products in the SO into individual dish lines."""
        self.ensure_one()
        guest_count = self.guest_count or 0

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

            # Show recommendation as a note line
            if catering_set.recommendation:
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'display_type': 'line_note',
                    'name': '💡 %s' % catering_set.recommendation,
                    'sequence': line.sequence + 1,
                })

            seq = line.sequence + 2
            current_section = None

            for set_line in catering_set.line_ids:
                # Insert section header when section changes
                if set_line.section and set_line.section != current_section:
                    current_section = set_line.section
                    self.env['sale.order.line'].create({
                        'order_id': self.id,
                        'display_type': 'line_section',
                        'name': current_section,
                        'sequence': seq,
                    })
                    seq += 1

                if not set_line.product_id:
                    continue

                # Determine auto-size based on guest count
                size_key = self._resolve_size(
                    catering_set, set_line, guest_count
                )
                price, actual_size = set_line.get_price_for_size(size_key)
                size_label = SIZE_LABELS.get(actual_size, actual_size)

                product_variant = set_line.product_id
                desc = set_line.description or product_variant.display_name
                if set_line.code:
                    desc = '%s %s' % (set_line.code, desc)

                # Qty: if per piece, default to guest count
                qty = set_line.qty or 1
                if actual_size == 'per_piece' and guest_count:
                    qty = guest_count

                # Main line (auto-sized, price=0 until selected)
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'product_id': product_variant.id,
                    'name': desc,
                    'product_uom_qty': qty,
                    'price_unit': 0,
                    'full_price': price,
                    'is_set_line': True,
                    'dish_selected': False,
                    'set_product_id': line.product_id.id,
                    'catering_set_id': catering_set.id,
                    'set_unit': size_label,
                    'set_line_code': set_line.code,
                    'eo_qty': set_line.eo_qty,
                    'eo_unit': set_line.eo_unit,
                    'per_piece_price': set_line.price_per_piece or 0,
                    'sequence': seq,
                })
                seq += 1

                # Add per-piece add-on line if:
                # - dish has a per-piece price, AND
                # - the main line is NOT already per-piece
                if set_line.price_per_piece and actual_size != 'per_piece':
                    addon_desc = '  ↳ Add-on (per piece)'
                    if set_line.code:
                        addon_desc = '  ↳ %s Add-on (per piece)' % set_line.code
                    self.env['sale.order.line'].create({
                        'order_id': self.id,
                        'product_id': product_variant.id,
                        'name': addon_desc,
                        'product_uom_qty': 0,
                        'price_unit': 0,
                        'full_price': set_line.price_per_piece,
                        'is_set_line': True,
                        'is_addon_piece': True,
                        'dish_selected': False,
                        'set_product_id': line.product_id.id,
                        'catering_set_id': catering_set.id,
                        'set_unit': 'Per piece',
                        'set_line_code': set_line.code,
                        'per_piece_price': set_line.price_per_piece,
                        'sequence': seq,
                    })
                    seq += 1

            # Set the original set line qty to 1, price to 0 (container)
            line.write({'product_uom_qty': 1, 'price_unit': 0})

    def _resolve_size(self, catering_set, set_line, guest_count):
        """Determine the right size key for a set line based on guest count."""
        size_group = set_line.size_group or 'salad_main'

        # Special rule for canapes: <20 guests = per piece
        if size_group == 'canapes' and guest_count < 20:
            if set_line.price_per_piece:
                return 'per_piece'

        # Use set's size rules
        auto_size = catering_set.get_auto_size(guest_count, size_group)
        if auto_size:
            return auto_size

        # Default fallback
        if size_group == 'canapes':
            return 'l_tray'
        return 'l_tray'

    def _get_selected_dish_count(self, catering_set_id, category_id):
        """Count how many dishes are selected for a set+category."""
        return len(self.order_line.filtered(
            lambda l: l.is_set_line
            and l.catering_set_id.id == catering_set_id
            and l.dish_selected
            and l.product_id.categ_id.id == category_id
        ))
