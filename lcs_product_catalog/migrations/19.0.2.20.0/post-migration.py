"""Batch 2 of the July 2026 client comments — C11, C13, C14.

Every file in lcs_product_catalog/data/ is <odoo noupdate="1">, so the new
fields added to the XML in this release do NOT reach an existing database.
Everything the running system needs is back-filled here.

  1. C11 — lcs.catering.set.line.is_package_fee on the 7 package-fee lines.
  2. C13 — lcs.catering.set.rule.section + .min_selection on the 27 shipped
           rules, keyed by XML ID so the values match the data files exactly
           rather than being guessed from label text.
  3. C13 — sale.order.line.set_section on already-expanded orders, so
           quotations already in the pipeline get the reminder too.
"""

from odoo import SUPERUSER_ID, api

# rule XML ID → (section, min_selection). Mirrors the data files exactly.
RULE_BACKFILL = {
    # Western Buffet
    'wb_rule_a': ('A. Salad / Appetizer 沙律/前菜 (Choose 2)', 2),
    'wb_rule_b': ('B. Party Snack 派對小食 (Choose 3, 40 pcs each)', 3),
    'wb_rule_c': ('C. Main Course 主菜 (Choose 3)', 3),
    'wb_rule_d': ('D. Vegetable Dish 蔬菜 (Choose 1)', 1),
    'wb_rule_e': ('E. Pasta & Risotto 意粉及燴飯 (Choose 2)', 2),
    'wb_rule_f': ('F. Dessert 甜品 (Choose 3, 30 pcs each)', 3),
    # Chinese Buffet
    'chb_rule_a': ('A. Salad / Appetizer 沙律/前菜 (Choose 2)', 2),
    'chb_rule_b': ('B. Party Snack 派對小食 (Choose 3, 40 pcs each)', 3),
    'chb_rule_c': ('C. Main Course 主菜 (Choose 3)', 3),
    'chb_rule_d': ('D. Vegetable Dish 蔬菜 (Choose 1)', 1),
    'chb_rule_e': ('E. Rice & Noodles 飯麵 (Choose 2)', 2),
    'chb_rule_f': ('F. Dessert 甜品 (Choose 3, 30 pcs each)', 3),
    # Cocktail Party — 4 priced tiers, so the tier pick stays and is enforced.
    'cp_rule_pkg': ('── Package Fee ── (Choose 1 tier)', 1),
    'cp_rule_cold': ('A. Cold Canapes 冷盤小食', 0),
    'cp_rule_warm': ('B. Warm Canapes 熱盤小食', 0),
    'cp_rule_veg': ('C. Vegetarian-Friendly 素食小食', 0),
    'cp_rule_asian': ('D. Asian Fusion 亞洲風味小食', 0),
    'cp_rule_sweet': ('E. Sweet Canapes 甜點小食', 0),
    # Grand Opening — sole fee line, so go_rule_pkg matches no SO line once
    # C11 folds the fee into the container. Harmless: sections with no lines
    # are skipped by _lcs_selection_breaches.
    'go_rule_pkg': ('── Package Fee ──', 1),
    'go_rule_pig': ('A. Suckling Pig 乳豬 (Choose 1)', 1),
    'go_rule_ceremonial': ('B. Ceremonial Items 開幕儀式食品 (included)', 0),
    'go_rule_canapes': ('C. Canapes 一口小食 (Choose 4, 40 pcs each)', 4),
    'go_rule_addons': ('D. Add-on Upgrades 升級項目 (optional)', 0),
    # Canape Box
    'cbx_mm_rule_box': ('── Box Tier ── (Choose 1)', 1),
    'cbx_mm_rule_cold': ('A. Cold Canapes 冷盤小食', 0),
    'cbx_mm_rule_warm': ('B. Warm Canapes 熱盤小食', 0),
    'cbx_mm_rule_sweet': ('C. Sweet Canapes 甜點小食', 0),
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # ── 1. C11: flag the package-fee lines ──
    # Matches the 3 sole fees (Western/Chinese Buffet, Grand Opening) and
    # Cocktail Party's 4 tiers. Canape Box's "── Box Tier ──" is deliberately
    # not matched: it is a box-size choice, not a per-person base fee, and
    # having several tiers it would be ignored by _get_sole_package_fee_line
    # either way.
    cr.execute(
        """
        UPDATE lcs_catering_set_line
           SET is_package_fee = TRUE
         WHERE section ILIKE %s
        """,
        ('%Package Fee%',),
    )

    # ── 2. C13: section + min_selection on the shipped rules ──
    for xmlid, (section, min_selection) in RULE_BACKFILL.items():
        rule = env.ref(
            'lcs_product_catalog.%s' % xmlid, raise_if_not_found=False
        )
        if rule:
            rule.write({'section': section, 'min_selection': min_selection})

    # ── 3. C13: set_section on already-expanded Sales Orders ──
    # Each dish line inherits the nearest preceding line_section header on the
    # same order. The running count of section headers gives every line a
    # group id; each group has exactly one header, so min(name) is that header.
    cr.execute(
        """
        WITH marked AS (
            SELECT id, order_id, display_type, name, is_set_line,
                   count(*) FILTER (WHERE display_type = 'line_section')
                       OVER (PARTITION BY order_id
                             ORDER BY sequence, id
                             ROWS UNBOUNDED PRECEDING) AS grp
              FROM sale_order_line
        ),
        sections AS (
            SELECT order_id, grp, min(name) AS sect
              FROM marked
             WHERE display_type = 'line_section'
             GROUP BY order_id, grp
        )
        UPDATE sale_order_line sol
           SET set_section = s.sect
          FROM marked m
          JOIN sections s ON s.order_id = m.order_id AND s.grp = m.grp
         WHERE sol.id = m.id
           AND sol.is_set_line IS TRUE
           AND sol.set_section IS NULL
        """
    )
