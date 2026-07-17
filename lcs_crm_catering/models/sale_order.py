from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
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
    call_van = fields.Selection(CALL_VAN_SELECTION, string='Preferred Driver')

    # Which opportunity time slot generated this quotation (Phase 2).
    origin_slot_id = fields.Many2one(
        'lcs.event.time.slot',
        string='Origin Time Slot',
        ondelete='set null', copy=False, index=True,
        help='The opportunity time slot this quotation was generated from.',
    )

    # ── Event / Delivery — single date + time window ──
    event_date = fields.Date(
        string='Event / Delivery Date',
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
        help='Duration of the event, in hours. Auto-derived from '
             'Event / Delivery Time (end - start) when both times are '
             'entered; still editable manually.',
    )

    @api.onchange('event_time_start', 'event_time_end')
    def _onchange_event_time_derive_hour(self):
        for order in self:
            if order.event_time_start and order.event_time_end \
                    and order.event_time_end > order.event_time_start:
                order.event_hour = order.event_time_end - order.event_time_start


    # ──────────────────────────────────────────────────────────
    # Waiter assignments (Event Catering only)
    # ──────────────────────────────────────────────────────────
    waiter_line_ids = fields.One2many(
        'lcs.sale.waiter.line', 'order_id', string='Waiters',
    )
    has_waiter_rows = fields.Boolean(
        compute='_compute_has_waiter_rows', store=True,
        help='True when the Waiter table has at least one row. Used by '
             'the view to gate readonly on # Waiters and Total Person-Hours.',
    )

    @api.depends('waiter_line_ids')
    def _compute_has_waiter_rows(self):
        for so in self:
            so.has_waiter_rows = bool(so.waiter_line_ids)

    # Both counters are plain editable fields. They auto-sync from the
    # Waiter table when the table has rows, and can be typed manually
    # when the table is empty. Either path also drives the Waiter Service
    # SO product line via _sync_waiter_service_line().
    waiter_count = fields.Integer(
        string='# Waiters', default=0,
        help='Number of waiters for the event. Auto-syncs to the Waiter '
             'table row count when the table has at least one row; '
             'otherwise editable manually.',
    )
    waiter_total_hours = fields.Float(
        string='Total Person-Hours', default=0.0, digits=(8, 2),
        help='Auto-syncs to the sum of hours in the Waiter table when it '
             'has rows. When the table is empty, auto-fills to '
             '# Waiters × Event Hour on change, and stays editable.',
    )

    @api.onchange('waiter_line_ids')
    def _onchange_waiter_line_ids_sync(self):
        """Auto-populate counters from the Waiter table when it has rows."""
        for order in self:
            if order.waiter_line_ids:
                order.waiter_count = len(order.waiter_line_ids)
                order.waiter_total_hours = sum(
                    order.waiter_line_ids.mapped('hours')
                )
            # else: leave manually-entered values in place

    @api.onchange('waiter_count', 'event_hour')
    def _onchange_waiter_count_derive_hours(self):
        """When user types # Waiters manually (no table rows), derive
        Total Person-Hours from # Waiters × Event Hour."""
        for order in self:
            if order.waiter_line_ids:
                # table drives the values; ignore manual count changes here
                continue
            if order.waiter_count and order.event_hour:
                order.waiter_total_hours = (
                    order.waiter_count * order.event_hour
                )

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
        """Maintain a "Waiter Service" section + product line on the SO.

        Driven by whichever data path the user chose:
          - Waiter table has rows → use its row count + summed hours.
          - Waiter table empty but waiter_count > 0 → use the manually-
            typed count and waiter_total_hours (auto-derived from
            # Waiters × Event Hour, or manually overridden).
          - Neither → no waiter line on the SO (any existing one is dropped).
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

            # Drop the waiter line if neither the table nor the manual
            # counters carry any signal.
            has_data = bool(order.waiter_line_ids) or (
                order.waiter_count > 0 and order.waiter_total_hours > 0
            )
            if not has_data:
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
        orders = super().create(vals_list)

        # Sync the Waiter Service section + product line on newly created SOs
        # whose Waiter tab was filled in at creation time (either via the
        # table, or via manually-typed # Waiters + Total Person-Hours).
        if not self.env.context.get('skip_waiter_sync'):
            for so in orders:
                if so.state == 'cancel':
                    continue
                if so.waiter_line_ids or (
                    so.waiter_count > 0 and so.waiter_total_hours > 0
                ):
                    so._sync_waiter_service_line()
        return orders

    def write(self, vals):
        res = super().write(vals)

        # Sync the "Waiter Service" SO line whenever any of its inputs move.
        if not self.env.context.get('skip_waiter_sync') and (
            {'waiter_count', 'waiter_total_hours', 'waiter_line_ids',
             'event_hour'} & set(vals)
        ):
            for so in self:
                if so.state != 'cancel':
                    so._sync_waiter_service_line()

        if 'call_van' in vals and not self.env.context.get('skip_call_van_sync'):
            for so in self:
                invs = so.invoice_ids.filtered(lambda i: i.state != 'cancel' and i.call_van != vals['call_van'])
                if invs:
                    invs.with_context(skip_call_van_sync=True).write({'call_van': vals['call_van']})
        return res

    @api.onchange('partner_id')
    def _onchange_partner_id_attention(self):
        """Default attention_to_id based on partner type."""
        if self.partner_id:
            if not self.partner_id.is_company:
                # Individual contact — default to themselves
                self.attention_to_id = self.partner_id
            else:
                self.attention_to_id = False

    # ──────────────────────────────────────────────────────────
    # Combined invoice — line-merge N ticked SOs into one account.move
    # ──────────────────────────────────────────────────────────
    def action_open_combined_invoice_wizard(self):
        """Open the payment-type wizard before creating the combined invoice."""
        if not self:
            raise UserError(_('No sales orders selected.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consolidated Billing'),
            'res_model': 'lcs.combined.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_ids': [(6, 0, self.ids)],
            },
        }

    def action_create_combined_invoice(self, payment_type='full',
                                       percentage=100.0, amount=0.0):
        """Create ONE draft invoice combining lines from every SO in self.

        payment_type:
          - 'full'       — full detail lines from every SO (default).
          - 'percentage' — a single "Consolidated Billing (X%)" line for
                           X% × total(all SOs).
          - 'amount'     — a single "Consolidated Billing" line for the
                           given amount.

        - All SOs must share the same billing partner.
        - All SOs must be confirmed (state in sale / done).
        - Catering header fields (brand, event_date, service_type, etc.) are
          copied from the FIRST SO.
        - Sections / notes: propagated only in 'full' mode.
        """
        if not self:
            raise UserError(_('No sales orders selected.'))

        # Validate: same billing partner across all SOs.
        billing_partners = set()
        for so in self:
            p = so.partner_invoice_id or so.partner_id
            if p:
                billing_partners.add(p.id)
        if len(billing_partners) > 1:
            raise UserError(_(
                'All selected orders must share the same billing customer. '
                'Selected orders reference %(n)d different customers.',
                n=len(billing_partners),
            ))

        # Validate: all confirmed.
        unconfirmed = self.filtered(lambda s: s.state not in ('sale', 'done'))
        if unconfirmed:
            raise UserError(_(
                'These orders are not confirmed and cannot be invoiced: %s',
                ', '.join(unconfirmed.mapped('name')),
            ))

        first = self[0]
        invoice_vals = first._prepare_invoice()
        invoice_vals['move_type'] = 'out_invoice'
        invoice_vals['invoice_origin'] = ', '.join(self.mapped('name'))

        invoice_lines = []
        if payment_type == 'full':
            # Full detail from every SO.
            invoiceable = self.filtered(
                lambda s: any((l.qty_to_invoice or 0) > 0
                              or (l.display_type and not l.qty_invoiced)
                              for l in s.order_line)
            )
            if not invoiceable:
                raise UserError(_(
                    'Every line on the selected orders is already fully invoiced.'
                ))
            for so in self:
                for line in so.order_line:
                    if line.display_type:
                        invoice_lines.append((0, 0, line._prepare_invoice_line()))
                        continue
                    qty = line.qty_to_invoice or 0
                    if qty <= 0:
                        continue
                    invoice_lines.append((0, 0, line._prepare_invoice_line(quantity=qty)))
            if not invoice_lines:
                raise UserError(_('Nothing to invoice on the selected orders.'))
        else:
            # Partial: a single line summarising the amount billed.
            total = sum(self.mapped('amount_total'))
            if payment_type == 'percentage':
                pct = float(percentage or 0.0)
                billed = total * pct / 100.0
                label = _('Consolidated Billing — %(pct).2f%% of %(t)s',
                          pct=pct, t=first.currency_id.symbol
                          and (first.currency_id.symbol + ('%.2f' % total))
                          or ('%.2f' % total))
            elif payment_type == 'amount':
                billed = float(amount or 0.0)
                label = _('Consolidated Billing — Fixed Amount')
            else:
                raise UserError(_('Unknown payment_type: %s') % payment_type)
            if billed <= 0:
                raise UserError(_('Computed billing amount is zero.'))
            invoice_lines.append((0, 0, {
                'name': '%s (SOs: %s)' % (label, ', '.join(self.mapped('name'))),
                'quantity': 1.0,
                'price_unit': billed,
                'display_type': 'product',
            }))

        invoice_vals['invoice_line_ids'] = invoice_lines
        move = self.env['account.move'].sudo().create(invoice_vals)

        # Log a note on every source SO.
        origin_names = ', '.join(self.mapped('name'))
        note_extra = ''
        if payment_type == 'percentage':
            note_extra = _(' — %(pct).2f%% billed', pct=float(percentage or 0.0))
        elif payment_type == 'amount':
            note_extra = _(' — fixed amount billed')
        for so in self:
            so.message_post(body=_(
                'Combined invoice %(inv)s created from %(orig)s%(extra)s',
                inv=move.name or move.display_name or move.id,
                orig=origin_names,
                extra=note_extra,
            ))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Combined Invoice'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
            'default_event_date': self.event_date,
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
