from odoo import fields, models


class EventOrderLine(models.Model):
    _name = 'lcs.event.order.line'
    _description = 'Event Order Line'
    _order = 'sequence, id'

    order_id = fields.Many2one(
        'lcs.event.order',
        string='Event Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    description = fields.Char(string='Description')
    so_qty = fields.Float(string='SO Qty', digits='Product Unit of Measure')
    kitchen_qty = fields.Float(string='Kitchen Qty', digits='Product Unit of Measure')
    kitchen_uom = fields.Char(string='Kitchen Unit')
    note = fields.Text(string='Note')
