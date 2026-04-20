from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CateringSet(models.Model):
    _name = 'lcs.catering.set'
    _description = 'Catering Set Menu'
    _order = 'sequence, name'

    name = fields.Char(string='Set Name', required=True)
    product_id = fields.Many2one(
        'product.template',
        string='Set Product',
        help='The product that represents this set in Sales Orders',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
    line_ids = fields.One2many(
        'lcs.catering.set.line', 'set_id', string='Available Dishes',
    )

    # Selection rules per category
    rule_ids = fields.One2many(
        'lcs.catering.set.rule', 'set_id', string='Selection Rules',
    )

    # Kitchen ratio tiers
    ratio_tier_ids = fields.One2many(
        'lcs.catering.set.ratio.tier', 'set_id', string='Kitchen Ratio Tiers',
    )


class CateringSetLine(models.Model):
    _name = 'lcs.catering.set.line'
    _description = 'Catering Set Dish Line'
    _order = 'category_id, sequence, id'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product', string='Dish', required=True,
    )
    category_id = fields.Many2one(
        'product.category', string='Category',
        related='product_id.categ_id', store=True,
    )
    sequence = fields.Integer(default=10)

    # Customer-facing (quotation / invoice)
    qty = fields.Float(string='Qty', digits='Product Unit of Measure', default=1.0)
    unit = fields.Char(string='Unit', help='e.g. pax, portion, set, pc')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')

    # Kitchen-facing (EO)
    eo_qty = fields.Float(string='EO Qty', digits='Product Unit of Measure')
    eo_unit = fields.Char(string='EO Unit', help='e.g. tray, litre, box, pan')

    description = fields.Char(
        string='Description',
        help='Override description for this dish in this set',
    )


class CateringSetRule(models.Model):
    _name = 'lcs.catering.set.rule'
    _description = 'Catering Set Selection Rule'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    category_id = fields.Many2one(
        'product.category', string='Category',
        help='Which dish category this rule applies to (e.g. A. Salad / Soup)',
    )
    max_selection = fields.Integer(
        string='Max Selection',
        help='Maximum number of dishes the customer can pick from this category. 0 = unlimited.',
        default=0,
    )
    label = fields.Char(
        string='Label',
        help='Display label, e.g. "Choose 2 Salads"',
    )


class CateringSetRatioTier(models.Model):
    _name = 'lcs.catering.set.ratio.tier'
    _description = 'Kitchen Ratio Tier (per guest count range)'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    category_id = fields.Many2one(
        'product.category', string='Dish Category',
        help='Which dish category this ratio applies to',
    )
    min_guests = fields.Integer(string='Min Guests', required=True)
    max_guests = fields.Integer(
        string='Max Guests',
        help='0 = no upper limit',
        default=0,
    )
    kitchen_unit = fields.Char(
        string='Kitchen Unit',
        help='e.g. tray, litre, pcs',
    )
    ratio = fields.Float(
        string='Guests per Unit',
        help='Number of guests served by 1 kitchen unit. '
             'E.g. 16 means 1 tray serves 16 guests.',
        default=1.0,
    )
    notes = fields.Char(string='Notes', help='e.g. "1/2 GN tray x 2"')
