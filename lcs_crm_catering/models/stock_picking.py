from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    event_day_offset = fields.Integer(
        string='Event Day Offset',
        default=0, copy=False,
        help='0-based day index of the multi-day catering event this delivery '
             'order serves. 0 = Day 1, 1 = Day 2, ... Populated when a '
             'multi-day SO is confirmed and its pooled picking is split '
             'per day. Also used by the Event Order picking linkage.',
    )
