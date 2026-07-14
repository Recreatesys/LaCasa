from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    time_slot_id = fields.Many2one(
        'lcs.event.time.slot',
        string='Time Slot',
        ondelete='set null', index=True, copy=False,
        help='Which SO time slot this delivery order serves. Set on SO '
             'confirm by _split_pickings_per_slot; used by EO linkage.',
    )
    event_day_offset = fields.Integer(
        string='Event Day Offset',
        default=0, copy=False,
        help='0-based day index. Auto-synced from time_slot_id.slot_offset '
             'when a slot is set. Kept for legacy compat with pre-slot data.',
    )
