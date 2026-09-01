from odoo import api, fields, models


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
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='SO Source Line',
        ondelete='set null',
        index=True,
        help='Originating sale order line; used by the SO→EO sync to '
             'match lines for diff/merge updates.',
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

    # ── C24 (client comment, slide 24): kitchen-facing filters ──
    product_categ_id = fields.Many2one(
        related='product_id.categ_id', store=True, string='Category',
    )
    is_food_item = fields.Boolean(
        string='Food Item',
        compute='_compute_is_food_item', store=True,
        help='True for lines the kitchen actually cooks. False for services '
             '(delivery charges, waiter service) and for storable equipment '
             '(utensils, hardware), which the chef has no dish to prepare for.',
    )

    def action_open_event_order(self):
        """Open the Event Order this dish line belongs to.

        Dish Overview is a read-only, grouped list of lcs.event.order.line, so
        clicking a row has nowhere useful to go — the line has no form view of
        its own, and a many2one cell in a list renders as plain text rather
        than a link. This gives the row an explicit way through to its EO.
        """
        self.ensure_one()
        if not self.order_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.order_id.display_name,
            'res_model': 'lcs.event.order',
            'res_id': self.order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('product_id', 'product_id.type', 'product_id.is_storable')
    def _compute_is_food_item(self):
        for line in self:
            product = line.product_id
            line.is_food_item = bool(
                product
                and product.type == 'consu'
                and not product.is_storable
            )
