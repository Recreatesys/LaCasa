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

    # Related fields from parent EO — stored so they support search/group/sort
    event_date = fields.Date(
        related='order_id.event_date', store=True, string='Event / Delivery Date',
    )
    partner_id = fields.Many2one(
        related='order_id.partner_id', store=True, string='Customer',
    )
    guest_count = fields.Integer(
        related='order_id.guest_count', store=True, string='No. of Guest',
    )
    brand = fields.Selection(
        related='order_id.brand', store=True, string='Brand',
    )
    service_format = fields.Selection(
        related='order_id.service_format', store=True, string='Service Format',
    )
    service_type = fields.Selection(
        related='order_id.service_type', store=True, string='Service Type',
    )
    delivery_type = fields.Selection(
        related='order_id.delivery_type', store=True, string='Delivery Type',
    )
    payment_status = fields.Selection(
        related='order_id.payment_status', store=True, string='Order Status',
    )
