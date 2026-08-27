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
        # product.template.name_search DOES route through here, so this alone
        # covers the product list, the catalog and any m2o onto templates.
        return _lcs_or_category_search(
            super()._search_display_name(operator, value), operator, value,
        )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Append category matches to the variant autocomplete.

        product.product.name_search does NOT go through _search_display_name —
        it hand-rolls its own cascade (default_code exact → barcode exact →
        default_code ilike → name ilike), so overriding _search_display_name
        alone has no effect on the Sales Order line's product field, which is
        exactly where slide 6 asked for this.

        Category hits are appended AFTER whatever the standard search found,
        so a product actually named "Dessert Platter" still outranks the
        dishes merely filed under Dessert, and they only fill the space left
        under `limit`.
        """
        res = super().name_search(name, domain, operator, limit)
        if not name or not isinstance(name, str):
            return res
        if operator in Domain.NEGATIVE_OPERATORS or not operator.endswith('like'):
            return res

        remaining = (limit - len(res)) if limit else None
        if remaining is not None and remaining <= 0:
            return res

        already = [r[0] for r in res]
        extra = self.search_fetch(
            Domain(domain or Domain.TRUE)
            & Domain('categ_id', operator, name)
            & Domain('id', 'not in', already),
            ['display_name'],
            limit=remaining,
        )
        return res + [(p.id, p.display_name) for p in extra]
