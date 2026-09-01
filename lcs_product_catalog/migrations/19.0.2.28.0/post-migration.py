"""Bring the Kitchen Ratio Tiers back to life.

Every one of the 150 tiers had category_id NULL, so get_ratio_tier could never
match a dish and no set line ever received an EO quantity or unit. Two faults
compounded:

  1. The data files DO declare category_id, but they are noupdate="1" and the
     tier records predate that field being added, so the value never reached
     the database. Same trap that hit min_guest_count and the selection rules.

  2. Those declarations point at the OLD flat categories ("A. Salad / Soup",
     "E. Main Dishes", ...). The C07 restructure moved every dish to the
     two-tier tree and left those holding zero products, so even a correct
     back-fill would still never match.

So the tiers are re-pointed at the new categories, using the mapping confirmed
with the client. get_ratio_tier now also walks up the category tree, so the
single "Canapes" tier covers Cold, Hot and Sweet.

Then the EO-side quantity and unit are re-derived on every active Event Order.
Only eo_qty / eo_unit and the EO line's kitchen_qty / kitchen_uom are touched
— never a quantity, price or invoice unit, so nothing quoted or billed moves.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# tier XML id -> new product category complete_name
TIER_CATEGORY = {
    "cbx_classic_ratio": "LCS Dishes / Canapes",
    "cbx_luxury_ratio": "LCS Dishes / Canapes",
    "cbx_mm_ratio": "LCS Dishes / Canapes",
    "chb_tier_appetizer_131_165": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_166_198": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_199_231": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_232_264": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_265_297": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_298_330": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_50_64": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_65_95": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_appetizer_96_130": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_canape_100_149": "LCS Dishes / Canapes",
    "chb_tier_canape_150_plus": "LCS Dishes / Canapes",
    "chb_tier_canape_50_99": "LCS Dishes / Canapes",
    "chb_tier_chicken_100_149": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_chicken_150_plus": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_chicken_50_99": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "chb_tier_main_100_149": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_main_150_plus": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_main_50_99": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_pasta_131_165": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_166_198": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_199_231": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_232_264": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_265_297": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_298_330": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_50_64": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_65_95": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_pasta_96_130": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "chb_tier_salad_131_165": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_166_198": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_199_231": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_232_264": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_265_297": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_298_330": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_50_64": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_65_95": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_salad_96_130": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "chb_tier_snack_100_149": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "chb_tier_snack_150_plus": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "chb_tier_snack_50_99": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "chb_tier_soup": "LCS Dishes / Tray Food / Buffet / Soup",
    "chb_tier_suckling_pig": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_131_165": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_166_198": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_199_231": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_232_264": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_265_297": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_298_330": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_50_64": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_65_95": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_veg_96_130": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_131_165": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_166_198": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_199_231": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_232_264": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_265_297": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_298_330": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_50_64": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_65_95": "LCS Dishes / Tray Food / Buffet / Main",
    "chb_tier_vegetable_96_130": "LCS Dishes / Tray Food / Buffet / Main",
    "cp_ratio_canapes": "LCS Dishes / Canapes",
    "cp_ratio_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "cp_ratio_party_snack": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "sdw_set_a_ratio_appetizer": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_a_ratio_canapes": "LCS Dishes / Canapes",
    "sdw_set_a_ratio_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "sdw_set_a_ratio_main": "LCS Dishes / Tray Food / Buffet / Main",
    "sdw_set_a_ratio_party_snack": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "sdw_set_a_ratio_rice_pasta": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "sdw_set_a_ratio_salad_soup": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_a_ratio_veg_fruits": "LCS Dishes / Tray Food / Buffet / Main",
    "sdw_set_b_ratio_appetizer": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_b_ratio_canapes": "LCS Dishes / Canapes",
    "sdw_set_b_ratio_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "sdw_set_b_ratio_main": "LCS Dishes / Tray Food / Buffet / Main",
    "sdw_set_b_ratio_party_snack": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "sdw_set_b_ratio_rice_pasta": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "sdw_set_b_ratio_salad_soup": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_b_ratio_veg_fruits": "LCS Dishes / Tray Food / Buffet / Main",
    "sdw_set_c_ratio_appetizer": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_c_ratio_canapes": "LCS Dishes / Canapes",
    "sdw_set_c_ratio_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "sdw_set_c_ratio_main": "LCS Dishes / Tray Food / Buffet / Main",
    "sdw_set_c_ratio_party_snack": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "sdw_set_c_ratio_rice_pasta": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "sdw_set_c_ratio_salad_soup": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "sdw_set_c_ratio_veg_fruits": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_appetizer_131_165": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_166_198": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_199_231": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_232_264": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_265_297": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_298_330": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_50_64": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_65_95": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_appetizer_96_130": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_canape_100_149": "LCS Dishes / Canapes",
    "wb_tier_canape_150_plus": "LCS Dishes / Canapes",
    "wb_tier_canape_50_99": "LCS Dishes / Canapes",
    "wb_tier_chicken_100_149": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_chicken_150_plus": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_chicken_50_99": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_dessert": "LCS Dishes / Tray Food / Buffet / Dessert",
    "wb_tier_main_100_149": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_main_150_plus": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_main_50_99": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_pasta_131_165": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_166_198": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_199_231": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_232_264": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_265_297": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_298_330": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_50_64": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_65_95": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_pasta_96_130": "LCS Dishes / Tray Food / Buffet / Rice / Pasta",
    "wb_tier_salad_131_165": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_166_198": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_199_231": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_232_264": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_265_297": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_298_330": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_50_64": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_65_95": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_salad_96_130": "LCS Dishes / Tray Food / Buffet / Appetizer",
    "wb_tier_snack_100_149": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "wb_tier_snack_150_plus": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "wb_tier_snack_50_99": "LCS Dishes / Tray Food / Buffet / Snack / Platter",
    "wb_tier_soup": "LCS Dishes / Tray Food / Buffet / Soup",
    "wb_tier_suckling_pig": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_131_165": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_166_198": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_199_231": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_232_264": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_265_297": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_298_330": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_50_64": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_65_95": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_veg_96_130": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_131_165": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_166_198": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_199_231": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_232_264": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_265_297": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_298_330": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_50_64": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_65_95": "LCS Dishes / Tray Food / Buffet / Main",
    "wb_tier_vegetable_96_130": "LCS Dishes / Tray Food / Buffet / Main"
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Category = env['product.category']

    # ── 1. re-point the tiers ──
    cache, repointed, unresolved = {}, 0, []
    for xmlid, complete_name in TIER_CATEGORY.items():
        tier = env.ref('lcs_product_catalog.%s' % xmlid, raise_if_not_found=False)
        if not tier:
            continue
        if complete_name not in cache:
            cache[complete_name] = Category.search(
                [('complete_name', '=', complete_name)], limit=1)
        category = cache[complete_name]
        if not category:
            unresolved.append(complete_name)
            continue
        if tier.category_id != category:
            tier.category_id = category
            repointed += 1
    _logger.info('C25: re-pointed %s ratio tier(s); unresolved categories: %s',
                 repointed, sorted(set(unresolved)) or 'none')

    # ── 2. re-derive kitchen qty/unit on every active Event Order ──
    orders = env['lcs.event.order'].search(
        [('payment_status', '!=', 'cancelled')]
    ).mapped('sale_order_id')
    changed = orders._lcs_refresh_kitchen_units()
    _logger.info('C25: refreshed EO qty/unit on %s sale order line(s) '
                 'across %s order(s)', changed, len(orders))

    # ── 3. push the corrected values onto the EO lines ──
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
                OR coalesce(l.kitchen_uom, '') IS DISTINCT FROM sol.eo_unit)
        """
    )
    _logger.info('C25: updated %s Event Order line(s)', cr.rowcount)
