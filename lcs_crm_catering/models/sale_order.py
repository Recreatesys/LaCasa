from odoo import _, api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    CALL_VAN_SELECTION,
    CLIENT_TYPE_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
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
    ('option_1', 'Option 1'),
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
    waiter_service = fields.Boolean(
        string='Waiter Service',
        help='Tick if this event requires waiter staffing. Reveals the Waiters tab.',
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

    # ── Event / Delivery — date range (multi-day events) ──
    event_date_start = fields.Date(
        string='Event / Delivery Date (Start)',
    )
    event_date_end = fields.Date(
        string='Event / Delivery Date (End)',
        help='Leave blank for a single-day event.',
    )
    event_day_count = fields.Integer(
        string='# Days',
        compute='_compute_event_day_count', store=True,
    )

    # ── Event / Delivery — time slot ──
    event_time_start = fields.Float(
        string='Event / Delivery Time (Start)',
        help='Time of day the event starts / delivery is due (HH:MM).',
    )
    event_time_end = fields.Float(
        string='Event / Delivery Time (End)',
        help='Time of day the event ends (HH:MM).',
    )
    # Back-compat alias — read by lcs_event_order sync and imports.
    delivery_time = fields.Float(
        string='Event / Delivery Time',
        related='event_time_start', store=True, readonly=False,
    )
    event_hour = fields.Float(
        string='Event Hour',
        help='Duration of the event, in hours.',
    )

    # Per-day One2many slices — one field per possible day (up to 7).
    # These are computed from order_line by filtering on event_day_offset.
    # Used by the multi-day notebook tabs.
    order_line_day_1 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 1',
    )
    order_line_day_2 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 2',
    )
    order_line_day_3 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 3',
    )
    order_line_day_4 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 4',
    )
    order_line_day_5 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 5',
    )
    order_line_day_6 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 6',
    )
    order_line_day_7 = fields.One2many(
        'sale.order.line', compute='_compute_order_line_by_day',
        inverse='_inverse_order_line_by_day', string='Order Lines — Day 7',
    )

    @api.depends('order_line', 'order_line.event_day_offset')
    def _compute_order_line_by_day(self):
        for so in self:
            grouped = {n: so.env['sale.order.line'] for n in range(7)}
            for line in so.order_line:
                offset = int(line.event_day_offset or 0)
                if 0 <= offset < 7:
                    grouped[offset] |= line
            so.order_line_day_1 = grouped[0]
            so.order_line_day_2 = grouped[1]
            so.order_line_day_3 = grouped[2]
            so.order_line_day_4 = grouped[3]
            so.order_line_day_5 = grouped[4]
            so.order_line_day_6 = grouped[5]
            so.order_line_day_7 = grouped[6]

    def _inverse_order_line_by_day(self):
        # Writing to a per-day slice already updates order_line via the shared
        # underlying model (each line is a real sale.order.line linked by order_id).
        # No separate write needed — the ORM handles it.
        return

    @api.depends('event_date_start', 'event_date_end')
    def _compute_event_day_count(self):
        for so in self:
            start = so.event_date_start
            end = so.event_date_end or start
            if not start:
                so.event_day_count = 0
            elif end < start:
                so.event_day_count = 1
            else:
                so.event_day_count = (end - start).days + 1

    @api.constrains('event_date_start', 'event_date_end')
    def _check_event_date_range(self):
        for so in self:
            if so.event_date_end and so.event_date_start and \
                    so.event_date_end < so.event_date_start:
                raise UserError(_(
                    'Event end date must be on or after the start date.'
                ))
            if so.event_day_count > 7:
                raise UserError(_(
                    'Event range is limited to 7 consecutive days.'
                ))

    # ──────────────────────────────────────────────────────────
    # Waiter assignments (Event Catering only)
    # ──────────────────────────────────────────────────────────
    waiter_line_ids = fields.One2many(
        'lcs.sale.waiter.line', 'order_id', string='Waiters',
    )
    waiter_count = fields.Integer(
        string='# Waiters', compute='_compute_waiter_totals', store=True,
    )
    waiter_total_hours = fields.Float(
        string='Total Person-Hours',
        compute='_compute_waiter_totals',
        store=True, digits=(8, 2),
    )

    @api.depends('waiter_line_ids', 'waiter_line_ids.hours')
    def _compute_waiter_totals(self):
        for order in self:
            order.waiter_count = len(order.waiter_line_ids)
            order.waiter_total_hours = sum(order.waiter_line_ids.mapped('hours'))

    # ──────────────────────────────────────────────────────────
    # Hardware (rented or sold goods listed on the SO)
    # ──────────────────────────────────────────────────────────
    hardware_line_ids = fields.One2many(
        'lcs.sale.hardware.line', 'order_id', string='Hardware',
    )
    hardware_total = fields.Monetary(
        string='Hardware Subtotal',
        compute='_compute_hardware_total',
        store=True,
    )

    @api.depends('hardware_line_ids', 'hardware_line_ids.price_subtotal')
    def _compute_hardware_total(self):
        for order in self:
            order.hardware_total = sum(order.hardware_line_ids.mapped('price_subtotal'))

    def _sync_hardware_lines(self):
        """Replace any existing auto-managed Hardware lines on order_line
        with a fresh "Hardware" section + one product line per hardware row.
        """
        SOL = self.env['sale.order.line']
        for order in self:
            if order.state == 'cancel':
                continue
            existing = order.order_line.filtered('is_hardware_line')
            existing.with_context(skip_hardware_sync=True).unlink()

            if not order.hardware_line_ids:
                continue

            SOL.with_context(skip_hardware_sync=True).create({
                'order_id': order.id,
                'name': 'Hardware',
                'display_type': 'line_section',
                'is_hardware_line': True,
                'sequence': 2000,
            })
            seq = 2001
            for hw in order.hardware_line_ids:
                SOL.with_context(skip_hardware_sync=True).create({
                    'order_id': order.id,
                    'product_id': hw.product_id.id,
                    'name': hw.product_id.display_name,
                    'product_uom_qty': hw.product_uom_qty,
                    'price_unit': hw.price_unit,
                    'is_hardware_line': True,
                    'sequence': seq,
                })
                seq += 1

    def _sync_waiter_service_line(self):
        """Maintain a "Waiter Service" section + product line on the SO,
        driven by the current waiter_line_ids.

        Quantity = sum of (end - start) across all waiter lines (person-hours).
        Price unit = the Waiter Service product's list price.
        """
        product_template = self.env.ref(
            'lcs_crm_catering.product_template_waiter_service',
            raise_if_not_found=False,
        )
        if not product_template:
            return
        product = product_template.product_variant_id
        if not product:
            return

        for order in self:
            if order.state == 'cancel':
                continue

            existing = order.order_line.filtered('is_waiter_service_line')
            existing_section = existing.filtered(lambda l: l.display_type == 'line_section')
            existing_product = existing.filtered(
                lambda l: not l.display_type and l.product_id == product
            )

            if not order.waiter_line_ids:
                existing.unlink()
                continue

            qty = order.waiter_total_hours
            section_name = _('Waiter Service (%(n)d staff, %(h).1f hrs total)') % {
                'n': order.waiter_count, 'h': order.waiter_total_hours,
            }

            if existing_section:
                if existing_section[0].name != section_name:
                    existing_section[0].with_context(skip_waiter_sync=True).name = section_name
            else:
                self.env['sale.order.line'].with_context(
                    skip_waiter_sync=True,
                ).create({
                    'order_id': order.id,
                    'name': section_name,
                    'display_type': 'line_section',
                    'is_waiter_service_line': True,
                    'sequence': 1000,
                })

            if existing_product:
                existing_product[0].with_context(skip_waiter_sync=True).write({
                    'product_uom_qty': qty,
                    'price_unit': product.list_price,
                })
            else:
                self.env['sale.order.line'].with_context(
                    skip_waiter_sync=True,
                ).create({
                    'order_id': order.id,
                    'product_id': product.id,
                    'name': product.display_name or _('Waiter Service'),
                    'product_uom_qty': qty,
                    'price_unit': product.list_price,
                    'is_waiter_service_line': True,
                    'sequence': 1001,
                })

    @api.model
    def _resolve_seq_prefix(self, brand, service_format, service_type,
                            no_logo, is_wedding):
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
        if service_format == 'event_catering':
            return 'lacasaE_N_' if no_logo else 'lacasaE'
        if service_format == 'food_delivery':
            return 'lacasaN' if no_logo else 'lacasa'
        return None

    @api.depends('brand', 'service_format', 'service_type',
                 'no_logo', 'is_wedding')
    def _compute_so_prefix_preview(self):
        for order in self:
            prefix = self._resolve_seq_prefix(
                order.brand, order.service_format, order.service_type,
                order.no_logo, order.is_wedding,
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
        # Shrink-guard: if the event date range shrinks, auto-remove SO lines
        # whose day_offset falls outside the new range, and cancel any
        # dependent Event Orders / Delivery Orders for those days.
        shrink_snapshot = {}
        if 'event_date_start' in vals or 'event_date_end' in vals:
            for so in self:
                if so.state in ('cancel',):
                    continue
                new_start = fields.Date.to_date(
                    vals.get('event_date_start', so.event_date_start)
                )
                new_end = fields.Date.to_date(
                    vals.get('event_date_end', so.event_date_end)
                )
                if not new_start:
                    continue
                if not new_end or new_end < new_start:
                    new_end = new_start
                new_count = (new_end - new_start).days + 1
                if new_count < (so.event_day_count or 1):
                    shrink_snapshot[so.id] = new_count

        res = super().write(vals)

        if shrink_snapshot:
            for so in self.browse(list(shrink_snapshot.keys())):
                so._prune_days_beyond(shrink_snapshot[so.id])

        if 'call_van' in vals and not self.env.context.get('skip_call_van_sync'):
            for so in self:
                invs = so.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.call_van != vals['call_van'])
                if invs:
                    invs.with_context(skip_call_van_sync=True).write({'call_van': vals['call_van']})
        return res

    def _prune_days_beyond(self, new_day_count):
        """Remove SO lines with event_day_offset >= new_day_count, and cancel
        any Event Orders + Delivery Orders scoped to those days.

        Called from write() when the date range shrinks. Post-message on the
        SO so the user has a clear audit trail.
        """
        self.ensure_one()
        removed_lines = self.order_line.filtered(
            lambda l: (l.event_day_offset or 0) >= new_day_count
        )
        if not removed_lines:
            return

        # Cancel matching pickings first (their procurement group encodes the day).
        Picking = self.env.get('stock.picking')
        cancelled_pickings = []
        if Picking is not None:
            for offset in range(new_day_count, self.event_day_count + 8):
                pg_name = '%s-D%d' % (self.name, offset + 1)
                pickings = Picking.search([
                    ('group_id.name', '=', pg_name),
                    ('state', 'not in', ('done', 'cancel')),
                ])
                if pickings:
                    pickings.action_cancel()
                    cancelled_pickings += pickings.mapped('name')

        # Cancel matching Event Orders.
        EO = self.env.get('lcs.event.order')
        cancelled_eos = []
        if EO is not None and 'event_day_offset' in EO._fields:
            eos = self.event_order_ids.filtered(
                lambda e: (e.event_day_offset or 0) >= new_day_count
            )
            if eos:
                cancelled_eos = eos.mapped('name')
                eos.unlink()

        removed_names = removed_lines.mapped('name')
        removed_lines.unlink()

        self.message_post(body=_(
            'Event range shrunk to %(days)d day(s). Auto-removed %(nlines)d '
            'SO line(s), cancelled %(neo)d Event Order(s) and %(npick)d '
            'Delivery Order(s).<br/>Removed lines: %(lines)s'
            '<br/>Cancelled EO: %(eos)s<br/>Cancelled DO: %(picks)s'
        ) % {
            'days': new_day_count,
            'nlines': len(removed_names),
            'neo': len(cancelled_eos),
            'npick': len(cancelled_pickings),
            'lines': ', '.join(removed_names[:20]) or '—',
            'eos': ', '.join(cancelled_eos) or '—',
            'picks': ', '.join(cancelled_pickings) or '—',
        })

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
            'waiter_service': self.waiter_service,
            'is_wedding': self.is_wedding,
        })
        return vals


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_waiter_service_line = fields.Boolean(
        string='Auto-Managed Waiter Service Line',
        default=False, copy=False,
        help='Marker for the section/product lines auto-generated from the Waiters tab.',
    )
    is_hardware_line = fields.Boolean(
        string='Auto-Managed Hardware Line',
        default=False, copy=False,
        help='Marker for the section/product lines auto-generated from the Hardware tab.',
    )

    # ── Multi-day event support ──
    event_day_offset = fields.Integer(
        string='Event Day',
        default=0, copy=True,
        help='0-based day within the SO event range. Day 1 = 0, Day 2 = 1, etc.',
    )
    event_date = fields.Date(
        string='Line Event Date',
        compute='_compute_event_date', store=True,
    )

    @api.depends('order_id.event_date_start', 'event_day_offset')
    def _compute_event_date(self):
        from datetime import timedelta
        for line in self:
            start = line.order_id.event_date_start
            if start:
                line.event_date = start + timedelta(days=line.event_day_offset or 0)
            else:
                line.event_date = False

    def _prepare_procurement_values(self, group_id=False):
        """Split procurement per event day so each day gets its own delivery order.

        A separate `procurement.group` per (SO, day_offset) forces stock rules
        to create a distinct `stock.picking` per day, each scheduled for its
        actual event day.
        """
        vals = super()._prepare_procurement_values(group_id=group_id)
        self.ensure_one()
        so = self.order_id
        if not so or (so.event_day_count or 0) < 2:
            return vals
        # Per-day procurement group
        offset = int(self.event_day_offset or 0)
        pg_name = '%s-D%d' % (so.name, offset + 1)
        pg = self.env['procurement.group'].search(
            [('name', '=', pg_name)], limit=1,
        )
        if not pg:
            pg_vals = so._prepare_procurement_group_vals() if hasattr(
                so, '_prepare_procurement_group_vals'
            ) else {}
            pg_vals.update({
                'name': pg_name,
                'sale_id': so.id,
                'partner_id': so.partner_shipping_id.id or so.partner_id.id,
            })
            pg = self.env['procurement.group'].create(pg_vals)
        vals['group_id'] = pg
        # Per-day scheduled date (event_date_start + offset at event_time_start).
        from datetime import datetime as _dt, timedelta as _td
        start_date = so.event_date_start
        if start_date:
            time_start = so.event_time_start or 0.0
            hours = int(time_start)
            minutes = int(round((time_start - hours) * 60))
            day_dt = _dt.combine(
                start_date + _td(days=offset), _dt.min.time(),
            ).replace(hour=hours, minute=minutes)
            vals['date_planned'] = day_dt
            vals['date_deadline'] = day_dt
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
            'default_event_date_start': self.event_date_start or self.event_date,
            'default_event_date_end': self.event_date_end,
            'default_event_time_start': self.event_time_start or self.delivery_time,
            'default_event_time_end': self.event_time_end,
            'default_commitment_date': self.event_date,
            'default_delivery_time': self.delivery_time,
            'default_event_hour': self.event_hour,
            'default_no_logo': self.no_logo,
            'default_waiter_service': self.waiter_service,
            'default_is_wedding': self.is_wedding,
            'default_call_van': self.call_van,
        })
        # Build delivery address
        if self.event_street:
            address_parts = [self.event_street]
            if self.event_street2:
                address_parts.append(self.event_street2)
            ctx['default_note'] = ctx.get('default_note', '') or ''
        return ctx
