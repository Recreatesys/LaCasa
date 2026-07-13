"""Migration: default event_day_offset=0 on all existing Event Orders.

Existing EOs were created from single-day SOs. Treat them as day 0
so all downstream logic (line filtering by day, picking lookup) works.
"""

def migrate(cr, version):
    cr.execute("""
        UPDATE lcs_event_order
           SET event_day_offset = 0
         WHERE event_day_offset IS NULL
    """)
