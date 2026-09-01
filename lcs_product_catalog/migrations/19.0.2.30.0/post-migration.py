"""Undo a mapping of mine that was too coarse.

19.0.2.28.0 re-pointed the ratio tiers onto the new two-tier categories, and
collapsed FIVE legacy categories onto "Tray Food / Buffet / Main":

    E. Main Dishes (9)  E1. Whole Chicken (6)  E2. Suckling Pig (2)
    F. Vegetables / Fresh Fruits (21)  F1. Vegetable (18)

The new tree has no equivalent of those sub-types, so all 56 tiers began
competing for the same category and get_ratio_tier returned whichever came
first. A braised beef cheek picked up the suckling-pig tier and the kitchen
was told to make "3.3 pcs".

The 47 sub-type tiers are parked here — category_id cleared, which returns
them to the inert state they were in before 28.0, and a note added so they can
be found. "E. Main Dishes" is left governing Main, being its direct
equivalent. Nothing is deleted: re-point any of them in
Sales > Configuration > Catering Sets > Kitchen Ratio Tiers.

Appetizer also has two sources (A. Salad / Soup and B. Appetizer, 21 each) but
their tiers are identical bracket for bracket, so that collision changes no
outcome and is left alone.

Then the kitchen quantity and unit are re-derived on every active Event Order,
since 28.0 computed them from the colliding tiers.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# tier XML id -> the legacy category it came from
PARKED_TIERS = {
    "chb_tier_chicken_100_149": "cat_whole_chicken",
    "chb_tier_chicken_150_plus": "cat_whole_chicken",
    "chb_tier_chicken_50_99": "cat_whole_chicken",
    "chb_tier_suckling_pig": "cat_suckling_pig",
    "chb_tier_veg_131_165": "cat_vegetables_fruits",
    "chb_tier_veg_166_198": "cat_vegetables_fruits",
    "chb_tier_veg_199_231": "cat_vegetables_fruits",
    "chb_tier_veg_232_264": "cat_vegetables_fruits",
    "chb_tier_veg_265_297": "cat_vegetables_fruits",
    "chb_tier_veg_298_330": "cat_vegetables_fruits",
    "chb_tier_veg_50_64": "cat_vegetables_fruits",
    "chb_tier_veg_65_95": "cat_vegetables_fruits",
    "chb_tier_veg_96_130": "cat_vegetables_fruits",
    "chb_tier_vegetable_131_165": "cat_vegetable",
    "chb_tier_vegetable_166_198": "cat_vegetable",
    "chb_tier_vegetable_199_231": "cat_vegetable",
    "chb_tier_vegetable_232_264": "cat_vegetable",
    "chb_tier_vegetable_265_297": "cat_vegetable",
    "chb_tier_vegetable_298_330": "cat_vegetable",
    "chb_tier_vegetable_50_64": "cat_vegetable",
    "chb_tier_vegetable_65_95": "cat_vegetable",
    "chb_tier_vegetable_96_130": "cat_vegetable",
    "sdw_set_a_ratio_veg_fruits": "cat_vegetables_fruits",
    "sdw_set_b_ratio_veg_fruits": "cat_vegetables_fruits",
    "sdw_set_c_ratio_veg_fruits": "cat_vegetables_fruits",
    "wb_tier_chicken_100_149": "cat_whole_chicken",
    "wb_tier_chicken_150_plus": "cat_whole_chicken",
    "wb_tier_chicken_50_99": "cat_whole_chicken",
    "wb_tier_suckling_pig": "cat_suckling_pig",
    "wb_tier_veg_131_165": "cat_vegetables_fruits",
    "wb_tier_veg_166_198": "cat_vegetables_fruits",
    "wb_tier_veg_199_231": "cat_vegetables_fruits",
    "wb_tier_veg_232_264": "cat_vegetables_fruits",
    "wb_tier_veg_265_297": "cat_vegetables_fruits",
    "wb_tier_veg_298_330": "cat_vegetables_fruits",
    "wb_tier_veg_50_64": "cat_vegetables_fruits",
    "wb_tier_veg_65_95": "cat_vegetables_fruits",
    "wb_tier_veg_96_130": "cat_vegetables_fruits",
    "wb_tier_vegetable_131_165": "cat_vegetable",
    "wb_tier_vegetable_166_198": "cat_vegetable",
    "wb_tier_vegetable_199_231": "cat_vegetable",
    "wb_tier_vegetable_232_264": "cat_vegetable",
    "wb_tier_vegetable_265_297": "cat_vegetable",
    "wb_tier_vegetable_298_330": "cat_vegetable",
    "wb_tier_vegetable_50_64": "cat_vegetable",
    "wb_tier_vegetable_65_95": "cat_vegetable",
    "wb_tier_vegetable_96_130": "cat_vegetable"
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    parked = 0
    for xmlid, legacy in PARKED_TIERS.items():
        tier = env.ref('lcs_product_catalog.%s' % xmlid, raise_if_not_found=False)
        if not tier or not tier.category_id:
            continue
        tier.write({
            'category_id': False,
            'notes': (tier.notes or '') + (
                ' [parked: came from %s, which has no equivalent in the '
                'two-tier category tree — re-point it to apply it]' % legacy
            ),
        })
        parked += 1
    _logger.info('C25: parked %s overlapping Main tier(s)', parked)

    orders = env['lcs.event.order'].search(
        [('payment_status', '!=', 'cancelled')]
    ).mapped('sale_order_id')
    changed = orders._lcs_refresh_kitchen_units()
    env.flush_all()
    _logger.info('C25: re-derived %s sale order line(s)', changed)

    cr.execute(
        """
        UPDATE lcs_event_order_line l
           SET kitchen_qty = sol.eo_qty,
               kitchen_uom = sol.eo_unit
          FROM sale_order_line sol, lcs_event_order eo
         WHERE sol.id = l.sale_line_id
           AND eo.id = l.order_id
           AND coalesce(eo.payment_status, '') <> 'cancelled'
           AND coalesce(sol.eo_qty, 0) <> 0
           AND coalesce(sol.eo_unit, '') <> ''
           AND (l.kitchen_qty IS DISTINCT FROM sol.eo_qty
                OR coalesce(l.kitchen_uom, '')
                   IS DISTINCT FROM coalesce(sol.eo_unit, ''))
        """
    )
    _logger.info('C25: updated %s Event Order line(s)', cr.rowcount)
