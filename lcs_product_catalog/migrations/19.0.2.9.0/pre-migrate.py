"""Delete legacy Chinese Buffet ratio_tier records and Mix & Match
canape size rules before the new XML data loads.

All targeted records are noupdate=1, so they survive a normal upgrade.
Without this pre-step, both old and new records would coexist and the
engine's first-match-wins lookup would be unpredictable.
"""

OLD_TIER_XMLIDS = [
    # Chinese Buffet legacy tiers — replaced by chb_tier_* fixed/formula
    'chb_ratio_salad_50', 'chb_ratio_salad_65', 'chb_ratio_salad_96',
    'chb_ratio_veg', 'chb_ratio_snack',
    'chb_ratio_main_50', 'chb_ratio_main_100', 'chb_ratio_main_150',
    'chb_ratio_starch', 'chb_ratio_dessert',
]

# Mix & Match canape size rules: replace with a single unbounded
# per_piece rule (1 pc per guest at any guest count).
OLD_SIZE_RULE_XMLIDS = [
    'size_rule_mm_9',
    'size_rule_mm_10',
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

    cr.execute(
        """
        DELETE FROM lcs_catering_set_size_rule
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'lcs_product_catalog'
              AND model = 'lcs.catering.set.size.rule'
              AND name = ANY(%s)
        )
        """,
        (OLD_SIZE_RULE_XMLIDS,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'lcs_product_catalog'
          AND model = 'lcs.catering.set.size.rule'
          AND name = ANY(%s)
        """,
        (OLD_SIZE_RULE_XMLIDS,),
    )
