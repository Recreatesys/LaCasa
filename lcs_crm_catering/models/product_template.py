from odoo import api, fields, models
from odoo.fields import Domain


GOODS_KIND_SELECTION = [
    ('sale', 'For Sale'),
    ('rental', 'For Rental'),
]


def _lcs_or_category_search(domain, operator, value):
    """C06 (client comment, slide 6): "When we search products, can we search
    by category".

    Widens a product name search so typing a category — "Dessert", "Canapes",
    "Meal Box" — also returns the dishes filed under it. product.category uses
    complete_name as its display name, so a partial match against
    "LCS Dishes / Tray Food / Buffet / Dessert" works on any segment of the
    path.

    Only positive `like` searches are widened. Negative operators keep their
    exact meaning (widening them would wrongly exclude records), and `in`
    lookups — which Odoo issues internally with a list of values — are left
    alone so nothing but the user's typing is affected.
    """
    if operator in Domain.NEGATIVE_OPERATORS:
        return domain
    if not operator.endswith('like'):
        return domain
    if not isinstance(value, str) or not value.strip():
        return domain
    return Domain.OR([domain, Domain('categ_id', operator, value)])


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    goods_kind = fields.Selection(
        GOODS_KIND_SELECTION,
        string='Goods Kind',
        default='sale',
        help='Distinguishes goods sold to the customer vs. goods rented out '
             'for an event (e.g. tables, chairs, equipment that comes back).',
    )

    @api.model
    def _search_display_name(self, operator, value):
        return _lcs_or_category_search(
            super()._search_display_name(operator, value), operator, value,
        )


class ProductProduct(models.Model):
    """Same widening for the variant model — that is what the Sales Order
    line's product field actually searches."""
    _inherit = 'product.product'

    @api.model
    def _search_display_name(self, operator, value):
        return _lcs_or_category_search(
            super()._search_display_name(operator, value), operator, value,
        )
