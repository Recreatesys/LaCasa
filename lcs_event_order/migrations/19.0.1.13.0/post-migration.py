"""Backfill lcs_event_order.time_slot_id from time slots seeded in
lcs_crm_catering's 19.0.1.49.0 migration.

lcs_crm_catering runs first (dependency order) and adds time_slot_id to
sale_order_line and stock_picking, backfilling them at that time. But
lcs_event_order's time_slot_id column doesn't exist yet at that point,
so the EO SIDE of the backfill has to happen here, once the column is
added by this module's schema update.

For each EO: find the parent SO's slot whose slot_offset matches the
EO's event_day_offset. Sets time_slot_id in bulk.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Skip if the column isn't there (shouldn't happen — this migration
    # runs AFTER the column is added — but be defensive).
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='lcs_event_order' AND column_name='time_slot_id'
    """)
    if not cr.fetchone():
        _logger.warning('lcs_event_order.time_slot_id missing; skipping backfill')
        return

    cr.execute("""
        UPDATE lcs_event_order eo
        SET time_slot_id = s.id
        FROM lcs_event_time_slot s
        WHERE s.sale_order_id = eo.sale_order_id
          AND s.slot_offset  = COALESCE(eo.event_day_offset, 0)
          AND eo.time_slot_id IS NULL
    """)
    _logger.info(
        'lcs_event_order slot backfill: %d EOs updated with time_slot_id',
        cr.rowcount,
    )
