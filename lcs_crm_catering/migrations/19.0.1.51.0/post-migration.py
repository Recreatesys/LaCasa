"""Multi-slot revert: seed sale_order.event_date from the legacy
event_date_start column.

We removed event_date_start / event_date_end / event_day_count /
time_slot_ids code paths on sale.order, but per the "leave columns in
place" decision the columns still exist. Add a plain event_date column
(Date) and copy event_date_start into it for existing rows so the SO
form's single-date field isn't blank.
"""


def migrate(cr, version):
    # Make sure the new event_date column exists (Odoo already creates it
    # from the field definition, but be defensive on migration ordering).
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='sale_order' AND column_name='event_date'
    """)
    if not cr.fetchone():
        return
    # Also check legacy source column exists (should on any migrated DB).
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='sale_order' AND column_name='event_date_start'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE sale_order
           SET event_date = event_date_start
         WHERE event_date IS NULL
           AND event_date_start IS NOT NULL
    """)
