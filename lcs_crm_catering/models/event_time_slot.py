from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EventTimeSlot(models.Model):
    _name = 'lcs.event.time.slot'
    _description = 'Event Time Slot'
    _order = 'sale_order_id, sequence, id'

    sale_order_id = fields.Many2one(
        'sale.order', string='Sales Order',
        required=True, ondelete='cascade', index=True,
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
        help='0-based position of this slot within its SO (ordered by sequence). '
             'Downstream models (SOL, picking, EO) mirror this for legacy compat.',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
    )

    @api.depends('sequence', 'sale_order_id')
    def _compute_slot_offset(self):
        """Position of this slot within its parent SO's ordered list of slots.

        Note: after the multi-slot revert, sale.order no longer exposes
        time_slot_ids, so this compute just leaves the offset at 0 for now.
        Phase 2 (opportunity slots) will rewire this to walk crm.lead's
        slot list.
        """
        for slot in self:
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
