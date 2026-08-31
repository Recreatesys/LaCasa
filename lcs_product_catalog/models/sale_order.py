import math

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
    is_lcs_delivery_line = fields.Boolean(
        string='Auto Delivery Charge', default=False, copy=False,
        help='Marker for the delivery line added by the delivery-zone '
             'lookup, so re-running it replaces its own line and leaves a '
             'hand-entered delivery charge alone.',
    )
    set_section = fields.Char(
        string='Set Section',
        help='The section of the catering set this dish came from, e.g. '
             '"F. Dessert 甜品 (Choose 3, 30 pcs each)". Stamped at expansion '
             'time so selection rules can be checked without inferring the '
             'section from line order, which breaks as soon as a user '
             'reorders or deletes a line.',
    )
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

    # ── C21b (client comment, slide 21): "Pls also show the cost of each
    #    food items." Internal-only — the SO line list is backend, and both
    #    columns are excluded from every customer-facing report. ──
    lcs_unit_cost = fields.Float(
        string='Unit Cost', related='product_id.standard_price',
        digits='Product Price', readonly=True,
        groups='sales_team.group_sale_salesman',
    )
    lcs_line_cost = fields.Monetary(
        string='Line Cost', compute='_compute_lcs_line_cost',
        currency_field='currency_id', readonly=True,
        groups='sales_team.group_sale_salesman',
    )
    lcs_margin_pct = fields.Float(
        string='Margin %', compute='_compute_lcs_line_cost',
        digits=(5, 1), readonly=True,
        groups='sales_team.group_sale_salesman',
        help='(Subtotal - Line Cost) / Subtotal. Blank when the line has no '
             'revenue (unpicked set dishes, section headers).',
    )

    @api.depends('product_uom_qty', 'lcs_unit_cost', 'price_subtotal')
    def _compute_lcs_line_cost(self):
        for line in self:
            cost = (line.product_uom_qty or 0.0) * (line.lcs_unit_cost or 0.0)
            line.lcs_line_cost = cost
            subtotal = line.price_subtotal or 0.0
            line.lcs_margin_pct = (
                (subtotal - cost) / subtotal * 100.0 if subtotal else 0.0
            )

    def write(self, vals):
        """C14 (client comment, slides 14-15): editing a set container's
        quantity resizes the dishes underneath it.

        The client's complaint was that changing the pax count from 50 to 100
        left every food line at 50. Rather than make them remember to press
        "Reload Sets", propagate on save.

        Scope is deliberately narrow:
          - Only when product_uom_qty actually changed.
          - Only on draft / sent orders. On a confirmed order this would
            silently rewrite billed quantities, so there "Reload Sets" stays
            the explicit, user-initiated path (_reload_sets_in_place).
          - Only for container lines — a line whose product IS a catering set.
            Dish lines are not containers and never trigger this.

        The lcs_skip_set_resize context key stops the resize's own writes from
        re-entering here.
        """
        res = super().write(vals)
        if 'product_uom_qty' not in vals or self.env.context.get('lcs_skip_set_resize'):
            return res

        for line in self:
            if line.display_type or line.is_set_line:
                continue
            if line.order_id.state not in ('draft', 'sent'):
                continue
            catering_set = self.env['lcs.catering.set'].search([
                ('product_id.product_variant_ids', 'in', [line.product_id.id]),
            ], limit=1)
            if not catering_set:
                continue
            line.order_id.with_context(
                lcs_skip_set_resize=True
            )._lcs_resize_set_dishes(catering_set, line)
        return res

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
        # Size the line straight away for a per-head set, so "80 guests"
        # shows as "80 x HK$398" without waiting for Expand Sets.
        fee_line = catering_set._get_per_person_fee_line()
        if fee_line and self.order_id:
            pax = self.order_id._lcs_pax_from_guest_count(catering_set)
            if pax:
                self.product_uom_qty = pax
            self.price_unit = fee_line.price_per_piece

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
        """Recalculate set-line quantities from the current guest count.

        Draft SOs: full rebuild (unlink existing set lines and re-expand).
        Confirmed / done SOs: in-place quantity update — Odoo blocks line
        deletion once an SO is confirmed, so we mirror the qty formula from
        action_expand_sets and write it back onto the existing lines.
        """
        self.ensure_one()
        if self.state != 'draft':
            return self._reload_sets_in_place()

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

    # ──────────────────────────────────────────────────────────
    # C14 — effective pax resolution and dish resizing
    # ──────────────────────────────────────────────────────────

    def _lcs_effective_pax(self, catering_set, container_line=None):
        """How many people this set is being sized for.

        C14 (slides 14-15): the client edits the quantity on the set's own
        line, so that line — not the order-level "No. of Guest" field — is the
        source of truth once it has been sized.

        Only for sets priced per head, though. On a flat-fee set (Grand
        Opening) or a multi-tier one, the container's quantity counts
        *packages*, not people — reading it as pax would size the dishes for 2
        guests because someone ordered 2 suckling-pig packages. Those keep
        guest_count as the source, exactly as before.

        A container still sitting at Odoo's default quantity of 1 has never
        been sized, so fall back to guest_count (the behaviour on first
        expansion). Keying off 1 is safe because the per-head sets are 50-pax
        minimum buffets — a sized container is never legitimately at 1.

        The per-set minimum always wins: a 30-guest Western Buffet still bills
        50 pax.
        """
        self.ensure_one()
        qty = 0
        if container_line and catering_set._get_per_person_fee_line():
            qty = int(container_line.product_uom_qty or 0)
        base = qty if qty > 1 else (self.guest_count or 0)
        return max(catering_set.min_guest_count or 0, base)

    def _lcs_set_line_qty(self, catering_set, set_line, effective_pax):
        """Quantity for one dish line at a given pax count.

        Single formula shared by expansion (action_expand_sets) and every
        resize path, so the two can't drift apart — they had already diverged
        once, which is part of why C14 was reported.
        """
        size_key = self._resolve_size(catering_set, set_line, effective_pax)
        _price, actual_size = set_line.get_price_for_size(size_key)

        qty = set_line.qty or 1
        if actual_size == 'per_piece' and effective_pax:
            qty = effective_pax

        category_id = set_line.product_id.categ_id.id if set_line.product_id else False
        ratio_tier = catering_set.get_ratio_tier(
            effective_pax, category_id
        ) if effective_pax else False
        if ratio_tier:
            mode = ratio_tier.tier_mode or 'ratio'
            if mode == 'fixed' and ratio_tier.invoice_qty:
                qty = ratio_tier.invoice_qty
            elif mode == 'formula' and ratio_tier.per_pax_qty:
                qty = math.ceil(effective_pax * ratio_tier.per_pax_qty)
            elif ratio_tier.invoice_unit and ratio_tier.ratio and ratio_tier.ratio > 0:
                qty = math.ceil(effective_pax / ratio_tier.ratio)
        return qty

    def _lcs_resize_set_dishes(self, catering_set, container_line):
        """Resize one set's dish lines to the container's pax count.

        Quantities only — prices, units, EO qty/unit and descriptions are left
        alone, and auto-managed per-piece add-ons are skipped because their
        quantity is the salesperson's choice.
        """
        self.ensure_one()
        effective_pax = self._lcs_effective_pax(catering_set, container_line)

        dish_sols = self.order_line.filtered(
            lambda l: l.is_set_line
            and not l.is_addon_piece
            and l.set_product_id == container_line.product_id
        )
        for sol in dish_sols:
            set_line = catering_set.line_ids.filtered(
                lambda sl: sl.product_id == sol.product_id
                and (sl.code or '') == (sol.set_line_code or '')
            )[:1]
            if not set_line:
                continue
            qty = self._lcs_set_line_qty(catering_set, set_line, effective_pax)
            if qty != sol.product_uom_qty:
                sol.with_context(lcs_skip_set_resize=True).product_uom_qty = qty

        # Keep the container honest — min_guest_count may have floored a
        # quantity the user typed below the set's minimum. Only for per-head
        # sets: on a flat-fee set (Grand Opening) the container quantity is 1
        # and writing the pax count there would multiply the package price.
        if (catering_set._get_per_person_fee_line()
                and container_line.product_uom_qty != effective_pax):
            container_line.with_context(
                lcs_skip_set_resize=True
            ).product_uom_qty = effective_pax

        # The Event Order reads order-level guest_count. Mirror the container
        # onto it only when this order carries a single set — with two sets at
        # different pax counts there is no one correct value.
        containers = self._lcs_get_set_containers()
        if len(containers) == 1 and self.guest_count != effective_pax:
            self.with_context(lcs_skip_set_resize=True).guest_count = effective_pax

    def _lcs_get_set_containers(self):
        """[(catering_set, container_line), …] for every set on this order.

        Found from the line's product, not from expanded dish lines, so a set
        that has been added but not yet expanded still counts. Keying off
        is_set_line would have missed exactly that case.
        """
        self.ensure_one()
        pairs = []
        CateringSet = self.env['lcs.catering.set']
        for line in self.order_line.filtered(
            lambda l: not l.display_type and not l.is_set_line and l.product_id
        ):
            catering_set = CateringSet.search([
                ('product_id.product_variant_ids', 'in', [line.product_id.id]),
            ], limit=1)
            if catering_set:
                pairs.append((catering_set, line))
        return pairs

    def _lcs_pax_from_guest_count(self, catering_set):
        """Pax implied by the order's No. of Guest, floored at the set minimum.

        Deliberately ignores the container's own quantity, unlike
        _lcs_effective_pax: this is the direction where the guest count is
        the input.
        """
        self.ensure_one()
        return max(catering_set.min_guest_count or 0, self.guest_count or 0)

    def _lcs_sync_containers_from_guest_count(self):
        """No. of Guest drives the set container's quantity.

        Until now the container only picked up the guest count inside
        action_expand_sets, so a set added to a quotation and left unexpanded
        sat at Odoo's default quantity of 1 — 80 guests, "Corporate Western
        Buffet x 1". The two now stay in step from the moment the set is
        added.

        Only per-head sets. A flat-fee container (Grand Opening, HK$16,388 for
        the event) must stay at 1, and a container with no package price is
        just a heading for its dish lines.
        """
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            for catering_set, container in order._lcs_get_set_containers():
                if not catering_set._get_per_person_fee_line():
                    continue
                pax = order._lcs_pax_from_guest_count(catering_set)
                if not pax or container.product_uom_qty == pax:
                    continue
                container.with_context(
                    lcs_skip_set_resize=True
                ).product_uom_qty = pax
                order.with_context(
                    lcs_skip_set_resize=True
                )._lcs_resize_set_dishes(catering_set, container)

    @api.onchange('guest_count')
    def _onchange_guest_count_sync_containers(self):
        self._lcs_sync_containers_from_guest_count()

    def write(self, vals):
        res = super().write(vals)
        if 'guest_count' in vals and not self.env.context.get('lcs_skip_set_resize'):
            self._lcs_sync_containers_from_guest_count()
        return res

    def _reload_sets_in_place(self):
        """Update existing set-line quantities WITHOUT unlinking (Odoo blocks
        line deletion once an SO is confirmed)."""
        self.ensure_one()
        for catering_set, container in self._lcs_get_set_containers():
            self._lcs_resize_set_dishes(catering_set, container)

    def action_open_set_picker(self):
        """Open a popup listing all active catering sets so the user can pick one."""
        self.ensure_one()
        ctx = {'active_order_id': self.id, 'create': False}
        return {
            'name': _('Pick a Catering Set'),
            'type': 'ir.actions.act_window',
            'res_model': 'lcs.catering.set',
            'view_mode': 'list',
            'view_id': self.env.ref(
                'lcs_product_catalog.lcs_catering_set_picker_view_list'
            ).id,
            'target': 'new',
            'domain': [('active', '=', True)],
            'context': ctx,
        }

    def action_expand_sets(self):
        """Expand set products in the SO into individual dish lines."""
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

            effective_guests = self._lcs_effective_pax(catering_set, line)

            # C11 (client comment, slide 11): when the set is priced as a
            # single per-person fee, that fee belongs on the container line
            # itself — the salesperson shouldn't have to scroll to a "Package
            # Fee" row and tick it. Sets offering several priced tiers keep
            # the pick; _get_sole_package_fee_line returns empty for those.
            fee_line = catering_set._get_sole_package_fee_line()

            # Pre-filter before the loop: section headers are emitted the
            # moment set_line.section changes, so dropping the fee line inside
            # the loop would leave an orphan "── Package Fee ──" header.
            set_lines = catering_set.line_ids
            if fee_line:
                set_lines = set_lines - fee_line

            # C12 (client comment, slide 12): the set's recommendation used
            # to be dropped in as a 💡 line_note here. The client doesn't want
            # that wording on the order lines (it also reached the customer's
            # quotation PDF). The text still reaches the salesperson via the
            # onchange warning when the set product is added, and lives on the
            # set record itself.
            seq = line.sequence + 2
            current_section = None

            for set_line in set_lines:
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
                    catering_set, set_line, effective_guests
                )
                price, actual_size = set_line.get_price_for_size(size_key)
                size_label = SIZE_LABELS.get(actual_size, actual_size)

                product_variant = set_line.product_id
                desc = set_line.description or product_variant.display_name
                if set_line.code:
                    desc = '%s %s' % (set_line.code, desc)

                # Qty: if per piece, default to guest count
                qty = set_line.qty or 1
                if actual_size == 'per_piece' and effective_guests:
                    qty = effective_guests

                # Look up ratio tier for SO/EO unit conversion
                eo_qty = set_line.eo_qty
                eo_unit = set_line.eo_unit
                category_id = product_variant.categ_id.id
                ratio_tier = catering_set.get_ratio_tier(
                    effective_guests, category_id
                ) if effective_guests else False

                if ratio_tier:
                    mode = ratio_tier.tier_mode or 'ratio'
                    if mode == 'fixed' and ratio_tier.invoice_qty:
                        # Explicit qty per bracket
                        qty = ratio_tier.invoice_qty
                        size_label = ratio_tier.invoice_unit or size_label
                        eo_qty = ratio_tier.kitchen_qty or qty
                        eo_unit = ratio_tier.kitchen_unit or eo_unit
                    elif mode == 'formula' and ratio_tier.per_pax_qty:
                        # Per-pax × guest count, EO adds extra qty
                        qty = math.ceil(
                            effective_guests * ratio_tier.per_pax_qty
                        )
                        size_label = ratio_tier.invoice_unit or size_label
                        eo_qty = qty + (ratio_tier.eo_extra_qty or 0)
                        eo_unit = ratio_tier.kitchen_unit or eo_unit
                    elif ratio_tier.invoice_unit:
                        # Existing ratio mode (backward compat)
                        if ratio_tier.ratio and ratio_tier.ratio > 0:
                            qty = math.ceil(
                                effective_guests / ratio_tier.ratio
                            )
                            size_label = ratio_tier.invoice_unit
                        if ratio_tier.conversion_factor:
                            eo_qty = qty * ratio_tier.conversion_factor
                            eo_unit = ratio_tier.kitchen_unit

                    # Secondary unit appended to invoice/SO description only.
                    if (ratio_tier.secondary_qty_per_pax
                            and ratio_tier.secondary_unit):
                        sec_qty = math.ceil(
                            effective_guests
                            * ratio_tier.secondary_qty_per_pax
                        )
                        desc = '%s (%s %s)' % (
                            desc, sec_qty, ratio_tier.secondary_unit,
                        )

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
                    'set_section': set_line.section,
                    'eo_qty': eo_qty,
                    'eo_unit': eo_unit,
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
                        'set_section': set_line.section,
                        'per_piece_price': set_line.price_per_piece,
                        'sequence': seq,
                    })
                    seq += 1

            # C11: the container carries the package fee when the set has a
            # single one — quantity is the pax count, price is the per-person
            # fee, so the salesperson sees "100 × $398" on the line they added.
            # Sets without a sole fee line keep the inert 1 × $0 container.
            if fee_line and fee_line.price_per_piece:
                # Per-person fee (Western / Chinese Buffet, HK$398/head):
                # quantity is the pax count, so the line reads "100 × $398".
                fee_qty = effective_guests
                fee_price = fee_line.price_per_piece
            elif fee_line:
                # Flat fee for the whole event (Grand Opening, HK$16,388).
                # Quantity stays 1 — pax must NOT multiply it.
                fee_qty = fee_line.qty or 1
                fee_price, _sz = fee_line.get_price_for_size('l_tray')
            else:
                fee_qty, fee_price = 1, 0
            line.with_context(lcs_skip_set_resize=True).write({
                'product_uom_qty': fee_qty, 'price_unit': fee_price,
            })

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

    # ──────────────────────────────────────────────────────────
    # C13 — selection rules ("Choose 3" actually means 3)
    # ──────────────────────────────────────────────────────────

    set_selection_warning = fields.Text(
        string='Set Selection Warning',
        compute='_compute_set_selection_warning',
        help='Lists every set section whose picked-dish count breaks its '
             'Min / Max Selection rule. Empty when the order is valid.',
    )

    @api.depends(
        'order_line.dish_selected', 'order_line.set_section',
        'order_line.catering_set_id', 'order_line.is_addon_piece',
    )
    def _compute_set_selection_warning(self):
        for order in self:
            order.set_selection_warning = '\n'.join(
                order._lcs_selection_breaches()
            )

    def _lcs_selection_breaches(self):
        """One human-readable line per section that is short or over.

        Rules are keyed by section, not by dish category: no rule record has
        ever carried a category_id, and a set's sections ("F. Dessert 甜品
        (Choose 3, 30 pcs each)") don't map 1:1 onto product categories.

        Sections with no matching rule are unconstrained and skipped, so
        orders expanded before set_section existed simply produce no warning
        rather than a false one.
        """
        self.ensure_one()
        breaches = []
        dish_lines = self.order_line.filtered(
            lambda l: l.is_set_line and not l.is_addon_piece and l.set_section
        )
        for catering_set in dish_lines.mapped('catering_set_id'):
            set_lines = dish_lines.filtered(
                lambda l, cs=catering_set: l.catering_set_id == cs
            )
            for rule in catering_set.rule_ids.filtered('section'):
                section_lines = set_lines.filtered(
                    lambda l, r=rule: l.set_section == r.section
                )
                if not section_lines:
                    continue
                picked = len(section_lines.filtered('dish_selected'))
                label = rule.label or rule.section
                if rule.min_selection and picked < rule.min_selection:
                    breaches.append(_(
                        '%(set_name)s — %(label)s: choose %(need)s, '
                        '%(picked)s selected.',
                        set_name=catering_set.name, label=label,
                        need=rule.min_selection, picked=picked,
                    ))
                elif rule.max_selection and picked > rule.max_selection:
                    breaches.append(_(
                        '%(set_name)s — %(label)s: at most %(need)s, '
                        '%(picked)s selected.',
                        set_name=catering_set.name, label=label,
                        need=rule.max_selection, picked=picked,
                    ))
        return breaches

    def action_confirm(self):
        """C13 (client comment, slide 13): "Only 2 items chosen but the system
        doesn't remind me." Block confirmation while any set is short or over,
        naming every offending section."""
        for order in self:
            breaches = order._lcs_selection_breaches()
            if breaches:
                raise UserError(_(
                    'This order does not satisfy its set selection rules:\n\n'
                    '%(details)s\n\n'
                    'Tick the missing dishes (or untick the extras) before '
                    'confirming.',
                    details='\n'.join('  • %s' % b for b in breaches),
                ))
        return super().action_confirm()

    # ──────────────────────────────────────────────────────────
    # C08 — delivery charge from the event address + delivery type
    # ──────────────────────────────────────────────────────────

    def _lcs_delivery_address_text(self):
        """Best available delivery address, as one block of text.

        Prefers the event address captured on the quotation, then the
        opportunity's, then the customer's delivery address — an event is
        rarely at the customer's registered office, so that is the last resort
        rather than the first.
        """
        self.ensure_one()
        for parts in (
            [self.event_street, self.event_street2],
            [self.opportunity_id.event_street,
             self.opportunity_id.event_street2] if self.opportunity_id else [],
            [self.partner_shipping_id.street,
             self.partner_shipping_id.street2,
             self.partner_shipping_id.city] if self.partner_shipping_id else [],
        ):
            text = ', '.join(p.strip() for p in parts if p and p.strip())
            if text:
                return text
        return ''

    def action_open_delivery_zone_wizard(self):
        """Open the Google Maps delivery-zone lookup."""
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_(
                'Delivery charges can only be set while the quotation is a '
                'draft.'
            ))
        return {
            'name': _('Locate Delivery Zone'),
            'type': 'ir.actions.act_window',
            'res_model': 'lcs.delivery.zone.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {**self.env.context, 'active_id': self.id},
        }

    def _lcs_apply_delivery_charge(self, product, zone, district, address=''):
        """Add the delivery line, replacing any previous zone-derived one.

        Only lines this wizard created are replaced — a delivery product a
        salesperson added by hand is left alone, because overwriting a
        negotiated charge without saying so would be worse than a duplicate.
        """
        self.ensure_one()
        existing = self.order_line.filtered('is_lcs_delivery_line')
        existing.unlink()

        note = _('%(zone)s — %(district)s') % {
            'zone': zone.name, 'district': district.name,
        }
        self.env['sale.order.line'].create({
            'order_id': self.id,
            'product_id': product.id,
            'name': '%s\n%s' % (product.display_name.split('\n')[0], note),
            'product_uom_qty': 1,
            'is_lcs_delivery_line': True,
            'sequence': 3000,
        })
        self.message_post(body=_(
            'Delivery charge set from the address lookup:<br/>'
            '<b>%(zone)s</b> (%(district)s) — %(product)s<br/>'
            '<span class="text-muted">%(address)s</span>',
            zone=zone.name, district=district.name,
            product=product.display_name.split('\n')[0],
            address=address or '',
        ))
