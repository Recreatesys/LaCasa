from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    kitchen_uom = fields.Char(
        string='Kitchen Unit',
        help='Unit used in Event Orders for the kitchen, e.g. tray, box, pan',
    )
    kitchen_ratio = fields.Float(
        string='Kitchen Ratio',
        default=1.0,
        help='SO qty / Kitchen Ratio = Kitchen qty. '
             'E.g. ratio=10 means 1 tray serves 10 pax.',
    )
