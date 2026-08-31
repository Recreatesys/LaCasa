"""File every existing catering-set container product under "LCS Set".

The 19 products that represent a catering set on a Sales Order (Corporate
Western Buffet, Mix & Match, Grand Opening Package, …) had no product category
at all. They are not dishes — they carry the package price and expand into
dish lines — so they do not belong under LCS Dishes either.

Going forward CateringSet._lcs_sync_set_product_category keeps this true as
sets are added or re-pointed; this back-fills what already exists.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    category = env.ref(
        'lcs_product_catalog.product_category_lcs_set', raise_if_not_found=False
    )
    if not category:
        _logger.warning('LCS Set category missing; nothing to back-fill.')
        return

    sets = env['lcs.catering.set'].with_context(active_test=False).search([])
    products = sets.mapped('product_id').filtered(lambda p: p.categ_id != category)
    if products:
        products.categ_id = category
    _logger.info(
        'LCS Set: filed %s container product(s) out of %s set(s)',
        len(products), len(sets),
    )
