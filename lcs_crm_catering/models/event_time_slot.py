from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EventTimeSlot(models.Model):
    _name = 'lcs.event.time.slot'
    _description = 'Event Time Slot'
    _order = 'crm_lead_id, sale_order_id, sequence, id'

    # Parent link — after Phase 1 revert, slots live on the opportunity.
    # sale_order_id is left nullable for legacy rows (pre-revert).
    crm_lead_id = fields.Many2one(
        'crm.lead', string='Opportunity',
        ondelete='cascade', index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order (legacy)',
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    label = fields.Char(
        string='Label', required=True, default='Slot 1',
        help='Free-text tag for this slot (e.g. "Breakfast", "Lunch", "Day 2").',
    )
    date = fields.Date(string='Date', required=True)
    time_start = fields.Float(
        string='Start', help='Time of day the slot starts (HH:MM).',
    )
    time_end = fields.Float(
        string='End', help='Time of day the slot ends (HH:MM).',
    )
    guest_count = fields.Integer(string='No. of Guest')
    slot_offset = fields.Integer(
        string='Slot Offset',
        compute='_compute_slot_offset', store=True,
        help='0-based position of this slot within its parent (opportunity or '
             'legacy SO), ordered by sequence.',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
    )
    # Back-link: the quotation created from this slot (Phase 2).
    order_id = fields.Many2one(
        'sale.order', string='Generated Quotation',
        ondelete='set null', copy=False, index=True,
    )

    @api.depends(
        'sequence',
        'crm_lead_id.time_slot_ids.sequence',
        'sale_order_id',
    )
    def _compute_slot_offset(self):
        """Position of this slot within its parent's ordered slot list."""
        parents = self.mapped('crm_lead_id') | self.mapped('sale_order_id')
        seen = set()
        for parent in parents:
            key = (parent._name, parent.id)
            if key in seen:
                continue
            seen.add(key)
            slots = parent.time_slot_ids.sorted('sequence') \
                if hasattr(parent, 'time_slot_ids') else self.env[self._name]
            for idx, slot in enumerate(slots):
                slot.slot_offset = idx
        # Slots with no parent → offset stays 0
        for slot in self:
            if not slot.crm_lead_id and not slot.sale_order_id:
                slot.slot_offset = 0

    @api.depends('label', 'date', 'time_start', 'time_end')
    def _compute_display_name(self):
        for slot in self:
            parts = []
            if slot.label:
                parts.append(slot.label)
            if slot.date:
                parts.append(fields.Date.to_string(slot.date))
            if slot.time_start or slot.time_end:
                def _fmt(f):
                    h = int(f or 0)
                    m = int(round(((f or 0) - h) * 60))
                    return '%02d:%02d' % (h, m)
                parts.append('%s-%s' % (_fmt(slot.time_start), _fmt(slot.time_end)))
            slot.display_name = ' — '.join(parts) if parts else _('Slot')

    @api.constrains('time_start', 'time_end')
    def _check_times(self):
        for slot in self:
            if slot.time_start and slot.time_end \
                    and slot.time_end < slot.time_start:
                raise ValidationError(_(
                    'Slot "%(label)s": end time must be on or after start time.',
                    label=slot.label or _('(unnamed)'),
                ))

    # ── Phase 2: auto-create a quotation on slot save ────────────────
    @api.model_create_multi
    def create(self, vals_list):
        slots = super().create(vals_list)
        for slot in slots:
            lead = slot.crm_lead_id
            if not lead or slot.order_id:
                continue
            # Only auto-create if the parent lead has already been "primed"
            # by an initial click of Create Quotations.
            if lead.quotations_created:
                slot._create_quotation_for_slot()
        return slots

    def _create_quotation_for_slot(self):
        """Create a draft Sales Order for this slot, inheriting the parent
        opportunity's catering defaults."""
        self.ensure_one()
        lead = self.crm_lead_id
        if not lead or self.order_id:
            return self.order_id
        SO = self.env['sale.order']
        vals = {
            'partner_id': lead.partner_id.id if lead.partner_id else False,
            'opportunity_id': lead.id,
            'origin_slot_id': self.id,
            'event_date': self.date,
            'event_time_start': self.time_start,
            'event_time_end': self.time_end,
            'guest_count': self.guest_count,
            'brand': lead.brand,
            'client_type': lead.client_type,
            'service_format': lead.service_format,
            'service_type': lead.service_type,
            'delivery_type': lead.delivery_type,
            'waiter_service': lead.waiter_service,
            'call_van': lead.call_van,
            'no_logo': lead.no_logo,
            'is_wedding': lead.is_wedding,
            'event_remark': lead.event_remark,
            'event_hour': lead.event_hour,
        }
        so = SO.create({k: v for k, v in vals.items() if v is not False and v is not None})
        self.order_id = so
        return so
