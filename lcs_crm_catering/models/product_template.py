from odoo import fields, models


GOODS_KIND_SELECTION = [
    ('sale', 'For Sale'),
    ('rental', 'For Rental'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    goods_kind = fields.Selection(
        GOODS_KIND_SELECTION,
        string='Goods Kind',
        default='sale',
        help='Distinguishes goods sold to the customer vs. goods rented out '
             'for an event (e.g. tables, chairs, equipment that comes back).',
    )
