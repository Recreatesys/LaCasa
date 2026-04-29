from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

SIZE_KEYS = ['per_piece', 'pn_1_1', 'pn_1_2', 's_tray', 'm_tray', 'l_tray', 'xl_tray']
SIZE_LABELS = {
    'per_piece': 'Per piece',
    'pn_1_1': '1/1 PN',
    'pn_1_2': '1/2 PN',
    's_tray': 'S tray',
    'm_tray': 'M tray',
    'l_tray': 'L tray',
    'xl_tray': 'XL tray',
}
# Ordered from smallest to largest for fallback logic
SIZE_ORDER = ['per_piece', 'pn_1_2', 's_tray', 'm_tray', 'l_tray', 'xl_tray', 'pn_1_1']


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
    recommendation = fields.Text(
        string='Recommended Selection',
        help='Internal remark shown to users, e.g. "2 appetizer + 2 snack + 3 main + 1 veg + 1-2 dessert"',
    )
    line_ids = fields.One2many(
        'lcs.catering.set.line', 'set_id', string='Available Dishes',
    )

    # Selection rules per category
    rule_ids = fields.One2many(
        'lcs.catering.set.rule', 'set_id', string='Selection Rules',
    )

    # Size auto-selection rules (guest count → size per category group)
    size_rule_ids = fields.One2many(
        'lcs.catering.set.size.rule', 'set_id', string='Size Rules',
    )

    # Kitchen ratio tiers
    ratio_tier_ids = fields.One2many(
        'lcs.catering.set.ratio.tier', 'set_id', string='Kitchen Ratio Tiers',
    )

    def action_add_to_active_order(self):
        """Add this set's product to the SO indicated by context['active_order_id']."""
        self.ensure_one()
        order_id = self.env.context.get('active_order_id')
        if not order_id:
            raise UserError(_('No active quotation in context.'))
        if not self.product_id:
            raise UserError(_(
                'The set "%s" has no product configured.'
            ) % self.name)
        product = self.product_id.product_variant_id
        if not product:
            raise UserError(_(
                'The set product "%s" has no variant available.'
            ) % self.product_id.display_name)
        self.env['sale.order.line'].create({
            'order_id': order_id,
            'product_id': product.id,
            'product_uom_qty': 1,
        })
        return {'type': 'ir.actions.act_window_close'}

    def get_ratio_tier(self, guest_count, category_id):
        """Find the matching ratio tier for a guest count and dish category.

        Returns the ratio tier record or False.
        """
        self.ensure_one()
        for tier in self.ratio_tier_ids.filtered(lambda t: t.category_id.id == category_id):
            max_g = tier.max_guests or 99999
            if tier.min_guests <= guest_count <= max_g:
                return tier
        return False

    def get_auto_size(self, guest_count, size_group):
        """Determine the auto-selected size based on guest count and size group.

        Args:
            guest_count: number of guests
            size_group: e.g. 'salad_main', 'pasta_rice', 'canapes'

        Returns:
            size key string (e.g. 'l_tray', 'per_piece') or False
        """
        self.ensure_one()
        for rule in self.size_rule_ids.filtered(lambda r: r.size_group == size_group):
            max_g = rule.max_guests or 99999
            if rule.min_guests <= guest_count <= max_g:
                return rule.size
        return False


class CateringSetLine(models.Model):
    _name = 'lcs.catering.set.line'
    _description = 'Catering Set Dish Line'
    _order = 'section, sequence, id'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    code = fields.Char(string='Code', help='e.g. A01, WC03, E08')
    product_id = fields.Many2one(
        'product.product', string='Dish',
    )
    category_id = fields.Many2one(
        'product.category', string='Category',
        related='product_id.categ_id', store=True,
    )
    section = fields.Char(
        string='Section',
        help='Section header, e.g. "Salad / Soup", "Cold Canapes"',
    )
    size_group = fields.Selection([
        ('salad_main', 'Salad & Main'),
        ('pasta_rice', 'Pasta & Rice'),
        ('canapes', 'Canapes / Snack / Dessert'),
    ], string='Size Group', default='salad_main',
        help='Determines which auto-size rule applies')
    sequence = fields.Integer(default=10)
    remark = fields.Char(string='Remark')

    # Multi-size pricing (HK$)
    price_per_piece = fields.Float(string='Per piece', digits='Product Price')
    price_pn_1_1 = fields.Float(string='1/1 PN', digits='Product Price')
    price_pn_1_2 = fields.Float(string='1/2 PN', digits='Product Price')
    price_s_tray = fields.Float(string='S tray', digits='Product Price')
    price_m_tray = fields.Float(string='M tray', digits='Product Price')
    price_l_tray = fields.Float(string='L tray', digits='Product Price')
    price_xl_tray = fields.Float(string='XL tray', digits='Product Price')

    # Customer-facing (set after auto-size resolution)
    qty = fields.Float(string='Qty', digits='Product Unit of Measure', default=1.0)
    unit = fields.Char(string='Unit')
    unit_price = fields.Float(string='Unit Price', digits='Product Price')

    # Kitchen-facing (EO)
    eo_qty = fields.Float(string='EO Qty', digits='Product Unit of Measure')
    eo_unit = fields.Char(string='EO Unit')

    description = fields.Char(
        string='Description',
        help='Override description for this dish in this set',
    )

    def get_price_for_size(self, size_key):
        """Get the price for a specific size. Returns (price, size_key) or fallback."""
        self.ensure_one()
        price = getattr(self, 'price_%s' % size_key, 0)
        if price:
            return price, size_key

        # Fallback: find next available size (go larger first, then smaller)
        idx = SIZE_ORDER.index(size_key) if size_key in SIZE_ORDER else 0
        # Try larger sizes first
        for i in range(idx + 1, len(SIZE_ORDER)):
            p = getattr(self, 'price_%s' % SIZE_ORDER[i], 0)
            if p:
                return p, SIZE_ORDER[i]
        # Then try smaller sizes
        for i in range(idx - 1, -1, -1):
            p = getattr(self, 'price_%s' % SIZE_ORDER[i], 0)
            if p:
                return p, SIZE_ORDER[i]
        return 0, size_key

    @property
    def has_per_piece_price(self):
        return bool(self.price_per_piece)


class CateringSetRule(models.Model):
    _name = 'lcs.catering.set.rule'
    _description = 'Catering Set Selection Rule'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    category_id = fields.Many2one(
        'product.category', string='Category',
        help='Which dish category this rule applies to',
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


class CateringSetSizeRule(models.Model):
    _name = 'lcs.catering.set.size.rule'
    _description = 'Size Auto-Selection Rule'
    _order = 'size_group, min_guests'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    size_group = fields.Selection([
        ('salad_main', 'Salad & Main'),
        ('pasta_rice', 'Pasta & Rice'),
        ('canapes', 'Canapes / Snack / Dessert'),
    ], string='Size Group', required=True)
    min_guests = fields.Integer(string='Min Guests', required=True)
    max_guests = fields.Integer(string='Max Guests', help='0 = no upper limit', default=0)
    size = fields.Selection([
        ('per_piece', 'Per piece'),
        ('pn_1_1', '1/1 PN'),
        ('pn_1_2', '1/2 PN'),
        ('s_tray', 'S tray'),
        ('m_tray', 'M tray'),
        ('l_tray', 'L tray'),
        ('xl_tray', 'XL tray'),
    ], string='Auto Size', required=True)


class CateringSetRatioTier(models.Model):
    _name = 'lcs.catering.set.ratio.tier'
    _description = 'Kitchen Ratio Tier (per guest count range)'
    _order = 'category_id, min_guests'

    set_id = fields.Many2one(
        'lcs.catering.set', string='Set', required=True, ondelete='cascade',
    )
    category_id = fields.Many2one(
        'product.category', string='Dish Category',
    )
    min_guests = fields.Integer(string='Min Guests', required=True)
    max_guests = fields.Integer(string='Max Guests', default=0)
    invoice_unit = fields.Char(
        string='SO/Invoice Unit',
        help='Unit shown on quotation/invoice, e.g. "1/2 GN tray", "pcs"',
    )
    kitchen_unit = fields.Char(
        string='EO Unit',
        help='Unit shown on Event Order for kitchen, e.g. "lb", "pcs"',
    )
    ratio = fields.Float(
        string='Guests per Invoice Unit', default=1.0,
        help='Number of guests served by 1 invoice unit. E.g. 16 means 1 tray per 16 pax.',
    )
    conversion_factor = fields.Float(
        string='EO per Invoice Unit', default=1.0,
        help='How many EO units per 1 invoice unit. E.g. 3.0 means 1 tray = 3 lb.',
    )
    notes = fields.Char(string='Notes')
