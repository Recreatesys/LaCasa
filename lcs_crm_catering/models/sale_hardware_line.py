from odoo import api, fields, models


class SaleHardwareLine(models.Model):
    _name = 'lcs.sale.hardware.line'
    _description = 'Sales Order Hardware Line'
    _order = 'sequence, id'

    order_id = fields.Many2one(
        'sale.order', string='Sales Order',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Hardware',
        required=True,
        domain="[('type', '=', 'consu'), ('is_storable', '=', True)]",
    )
    goods_kind = fields.Selection(
        related='product_id.product_tmpl_id.goods_kind',
        string='Kind', readonly=True, store=True,
    )
    product_uom_qty = fields.Float(
        string='Quantity', default=1.0, digits='Product Unit of Measure',
    )
    availability = fields.Float(
        string='Availability (On Hand)',
        related='product_id.qty_available',
        readonly=True,
    )
    price_unit = fields.Float(
        string='Unit Price', digits='Product Price',
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id', readonly=True,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id and not line.price_unit:
                line.price_unit = line.product_id.list_price

    @api.model_create_multi
    def create(self, vals_list):
        # Default price_unit from product if missing
        for vals in vals_list:
            if not vals.get('price_unit') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['price_unit'] = product.list_price or 0.0
        lines = super().create(vals_list)
        lines.mapped('order_id')._sync_hardware_lines()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self.mapped('order_id')._sync_hardware_lines()
        return res

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        orders._sync_hardware_lines()
        return res
