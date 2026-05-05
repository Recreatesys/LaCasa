"""Post-migration tweaks:

- Reclassify dishes whose categ_id changed in this version. master_dishes.xml
  records are noupdate=1, so the new categ_id from XML is not applied to
  existing rows; we have to UPDATE directly.
- Set min_guest_count=50 on Corporate Chinese Buffet (the WB minimum is
  set in the XML; CB's set record is also noupdate=1).
"""

# Map of new category xmlid → list of dish xmlids that must move into it.
RECLASS = {
    'cat_soup': [
        'dish_012',     # Truffle Wild Mushroom Cream Soup (master_dishes.xml)
        'dish_wb_02',   # Lobster Bisque (western_buffet_set.xml)
    ],
    'cat_whole_chicken': ['dish_093'],   # Roasted Chicken with Rosemary Sauce
    'cat_suckling_pig': ['dish_102'],    # Spanish Suckling Pig
    'cat_vegetable': [
        'dish_127',  # Grilled Mixed Vegetables (V)
        'dish_128',  # Cheesy Vegetable Bake (V)
        'dish_129',  # Shanghai Cabbage with Crispy Parma Ham
        'dish_130',  # Grilled Portobello & Mixed Vegetables (V)
        'dish_131',  # Sauteed Mushroom & Broccoli with Garlic (V)
        'dish_132',  # Japanese Stir-fried Mixed Vegetables (v)
        'dish_134',  # Poached Vegetable and Bean Curd Sheet in Fish Soup
        'dish_135',  # Mushrooms Medley (Winter Melon etc.)
    ],
}


def _xmlid_to_id(cr, model, names):
    cr.execute(
        """
        SELECT name, res_id FROM ir_model_data
        WHERE module = 'lcs_product_catalog'
          AND model = %s
          AND name = ANY(%s)
        """,
        (model, list(names)),
    )
    return {r[0]: r[1] for r in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return

    for cat_xmlid, dish_xmlids in RECLASS.items():
        cat_map = _xmlid_to_id(cr, 'product.category', [cat_xmlid])
        if cat_xmlid not in cat_map:
            continue
        cat_id = cat_map[cat_xmlid]
        dish_map = _xmlid_to_id(cr, 'product.template', dish_xmlids)
        tmpl_ids = list(dish_map.values())
        if tmpl_ids:
            cr.execute(
                "UPDATE product_template SET categ_id = %s WHERE id = ANY(%s)",
                (cat_id, tmpl_ids),
            )

    # Set min_guest_count=50 on Chinese Buffet (CB's set record is
    # noupdate=1 so XML changes don't apply).
    cr.execute(
        """
        UPDATE lcs_catering_set
        SET min_guest_count = 50
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'lcs_product_catalog'
              AND model = 'lcs.catering.set'
              AND name = 'set_chinese_buffet'
        )
        """
    )
