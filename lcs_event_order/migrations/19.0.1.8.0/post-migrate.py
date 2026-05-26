"""Backfill `sale_line_id` on legacy EO lines.

Match each EO line that lacks a `sale_line_id` to a sale.order.line on the
EO's parent SO, using (product_id, description) as the key. Pairs are
matched 1:1 in deterministic order so duplicate products on the same SO
each get their own match.
"""


def migrate(cr, version):
    cr.execute("""
        SELECT id, sale_order_id
        FROM lcs_event_order
        WHERE id IN (
            SELECT DISTINCT order_id
            FROM lcs_event_order_line
            WHERE sale_line_id IS NULL
        )
    """)
    eo_rows = cr.fetchall()
    matched = 0
    for eo_id, so_id in eo_rows:
        if not so_id:
            continue

        # Pull candidate SO lines (excluding display-type rows)
        cr.execute("""
            SELECT id, product_id, name
            FROM sale_order_line
            WHERE order_id = %s
              AND (display_type IS NULL OR display_type = '')
            ORDER BY sequence, id
        """, (so_id,))
        sol_rows = cr.fetchall()

        # Pull EO lines needing a match
        cr.execute("""
            SELECT id, product_id, description
            FROM lcs_event_order_line
            WHERE order_id = %s AND sale_line_id IS NULL
            ORDER BY sequence, id
        """, (eo_id,))
        eo_lines = cr.fetchall()

        consumed = set()
        for eo_line_id, eo_product_id, eo_desc in eo_lines:
            best = None
            for sol_id, sol_product_id, sol_name in sol_rows:
                if sol_id in consumed:
                    continue
                if sol_product_id != eo_product_id:
                    continue
                # Prefer exact description match; fall back to product-only
                if (eo_desc or '') == (sol_name or ''):
                    best = sol_id
                    break
                if best is None:
                    best = sol_id
            if best is not None:
                consumed.add(best)
                cr.execute(
                    "UPDATE lcs_event_order_line SET sale_line_id = %s WHERE id = %s",
                    (best, eo_line_id),
                )
                matched += 1

    cr.execute("SELECT COUNT(*) FROM lcs_event_order_line WHERE sale_line_id IS NULL")
    remaining = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM lcs_event_order_line")
    total = cr.fetchone()[0]
    import logging
    logging.getLogger(__name__).info(
        "lcs_event_order backfill: matched %d EO lines; %d / %d still without sale_line_id",
        matched, remaining, total,
    )
