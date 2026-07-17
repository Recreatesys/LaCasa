# Stock picking extension — currently empty after the multi-slot revert.
# Legacy columns (time_slot_id, event_day_offset) are left in the DB per
# the "leave columns in place, drop code" decision; nothing reads them.

from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'
