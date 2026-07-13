"""Migration: seed event_date_start / event_time_start on existing records.

The legacy `event_date` (crm.lead) and `commitment_date` / `delivery_time`
(sale.order) columns are kept as related fields to the new *_start columns.
For rows created before this migration, copy the legacy values across so
the new UI has data to display.

Idempotent: only copies when the *_start column is null.
"""

def migrate(cr, version):
    # crm.lead — copy event_date (Date) into event_date_start.
    cr.execute("""
        UPDATE crm_lead
           SET event_date_start = event_date
         WHERE event_date IS NOT NULL
           AND event_date_start IS NULL
    """)
    # sale.order — commitment_date is Datetime; take its Date part.
    cr.execute("""
        UPDATE sale_order
           SET event_date_start = commitment_date::date
         WHERE commitment_date IS NOT NULL
           AND event_date_start IS NULL
    """)
    # delivery_time (Float) → event_time_start (Float)
    # (columns exist because both are stored, delivery_time is a related-store
    #  alias in the new model; ensure the start column is seeded for legacy rows).
    cr.execute("""
        UPDATE sale_order
           SET event_time_start = delivery_time
         WHERE delivery_time IS NOT NULL
           AND (event_time_start IS NULL OR event_time_start = 0)
    """)
    cr.execute("""
        UPDATE crm_lead
           SET event_time_start = delivery_time
         WHERE delivery_time IS NOT NULL
           AND (event_time_start IS NULL OR event_time_start = 0)
    """)
    # sale.order.line — all legacy lines default to day 0 (single-day event).
    cr.execute("""
        UPDATE sale_order_line
           SET event_day_offset = 0
         WHERE event_day_offset IS NULL
    """)
