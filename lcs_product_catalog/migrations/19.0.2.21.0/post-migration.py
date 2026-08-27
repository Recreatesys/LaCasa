"""Re-sync lcs.catering.set.min_guest_count from the data files.

Found while verifying C14 on LaCasa_Odoo19: set_western_buffet declares
min_guest_count=50 in western_buffet_set.xml, but the live record held 0. The
data files are <odoo noupdate="1">, so the value was never applied — the
minimum was added to the XML after the record already existed.

The effect was that the Western Buffet's "minimum order 50 pax" — stated in
its own customer-facing recommendation text, and already enforced on the
otherwise-identical Chinese Buffet — was silently ignored: a 30-guest order
was sized and priced for 30. This corrects that, and makes the two buffets
behave the same way.

Only records that declare a minimum are touched; every other set declares 0
and is left alone.
"""

MIN_GUEST_COUNTS = {
    'set_western_buffet': 50,
    'set_chinese_buffet': 50,
}


def migrate(cr, version):
    for xmlid, minimum in MIN_GUEST_COUNTS.items():
        cr.execute(
            """
            UPDATE lcs_catering_set s
               SET min_guest_count = %s
              FROM ir_model_data d
             WHERE d.model = 'lcs.catering.set'
               AND d.module = 'lcs_product_catalog'
               AND d.name = %s
               AND d.res_id = s.id
               AND s.min_guest_count IS DISTINCT FROM %s
            """,
            (minimum, xmlid, minimum),
        )
