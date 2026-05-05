"""Delete the old Western Buffet ratio_tier records before reload.

These records are noupdate=1 and would otherwise survive the upgrade,
producing duplicate / conflicting tiers alongside the new wb_tier_*
fixed/formula tiers loaded from western_buffet_set.xml.
"""

OLD_TIER_XMLIDS = [
    'wb_ratio_salad_50',
    'wb_ratio_salad_65',
    'wb_ratio_salad_96',
    'wb_ratio_veg',
    'wb_ratio_snack',
    'wb_ratio_main_50',
    'wb_ratio_main_100',
    'wb_ratio_main_150',
    'wb_ratio_starch',
    'wb_ratio_dessert',
]


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        DELETE FROM lcs_catering_set_ratio_tier
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'lcs_product_catalog'
              AND model = 'lcs.catering.set.ratio.tier'
              AND name = ANY(%s)
        )
        """,
        (OLD_TIER_XMLIDS,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'lcs_product_catalog'
          AND model = 'lcs.catering.set.ratio.tier'
          AND name = ANY(%s)
        """,
        (OLD_TIER_XMLIDS,),
    )
