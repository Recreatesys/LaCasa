"""Post-migration tweaks for Chinese Buffet alignment.

Reclassifies Chinese soup and whole-chicken dishes whose categ_id
changed in this version. All these records are noupdate=1 so the new
categ_id from XML is not applied to existing rows.
"""

# Map of new category xmlid → list of dish xmlids that must move into it.
RECLASS = {
    'cat_soup': [
        'dish_010',     # Assorted Seafood in Dried Scallop Soup
        'dish_011',     # Assorted Seafood Soup
        'dish_013',     # Chicken Soup with Conpoy, Conch & Fish Maw
        'dish_cb_03',   # Corn & Fish Maw Thick Soup (chinese_buffet_set.xml)
    ],
    'cat_whole_chicken': [
        'dish_095',     # Steamed Chicken with Ginger and Scallion (CB)
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
