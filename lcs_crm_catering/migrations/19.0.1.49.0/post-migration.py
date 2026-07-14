"""Populate lcs.event.time.slot for existing SOs and backfill time_slot_id.

For every SO with catering event data:
- Create N time slots (1 if single-day / no dates, N if multi-day).
- Populate label ("Day 1"…"Day N" or "Slot 1"), date, times, guest count.
- For each SOL, picking, EO on that SO: set time_slot_id by matching
  event_day_offset against the slot's slot_offset (position within SO).

Runs in a savepoint per SO so a single bad row won't abort the whole
migration.
"""
import logging
from datetime import date, timedelta

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Slot = env['lcs.event.time.slot']
    SO = env['sale.order']
    Picking = env.get('stock.picking')
    EO = env.get('lcs.event.order')

    # Only SOs that don't already have slots (idempotent).
    sos = SO.search([('time_slot_ids', '=', False)])
    _logger.info('lcs_crm_catering slot migration: %d SOs to seed', len(sos))
    seeded = 0
    for so in sos:
        try:
            with cr.savepoint():
                # Decide the number of slots per SO.
                # 1) If SO lines/picking/EO reference offsets > event_day_count-1
                #    (imported / hand-edited), honour the max of those.
                # 2) Otherwise use max(event_day_count, 1).
                declared = max(1, min(so.event_day_count or 1, 7))
                observed = {int(l.event_day_offset or 0) for l in so.order_line}
                if Picking is not None:
                    observed |= {int(p.event_day_offset or 0)
                                 for p in Picking.search([('sale_id', '=', so.id)])}
                if EO is not None:
                    observed |= {int(e.event_day_offset or 0)
                                 for e in so.event_order_ids}
                # Clamp to [0, 6] and derive count.
                observed = {o for o in observed if 0 <= o <= 6}
                needed = max(declared, (max(observed) + 1) if observed else 1)
                needed = min(needed, 7)

                start = so.event_date_start or date.today()
                slots_by_offset = {}
                for offset in range(needed):
                    label = ('Day %d' % (offset + 1)) if needed > 1 else 'Slot 1'
                    slot = Slot.create({
                        'sale_order_id': so.id,
                        'label': label,
                        'sequence': 10 * (offset + 1),
                        'date': start + timedelta(days=offset),
                        'time_start': so.event_time_start or 0.0,
                        'time_end': so.event_time_end or 0.0,
                        'guest_count': so.guest_count or 0,
                    })
                    slots_by_offset[offset] = slot.id

                # Backfill SOLs
                for line in so.order_line:
                    off = int(line.event_day_offset or 0)
                    if off in slots_by_offset:
                        cr.execute(
                            "UPDATE sale_order_line SET time_slot_id=%s WHERE id=%s",
                            (slots_by_offset[off], line.id),
                        )

                # Backfill pickings (v19)
                if Picking is not None:
                    for pk in Picking.search([('sale_id', '=', so.id)]):
                        off = int(pk.event_day_offset or 0)
                        if off in slots_by_offset:
                            cr.execute(
                                "UPDATE stock_picking SET time_slot_id=%s WHERE id=%s",
                                (slots_by_offset[off], pk.id),
                            )

                # Backfill EOs
                if EO is not None:
                    for eo in so.event_order_ids:
                        off = int(eo.event_day_offset or 0)
                        if off in slots_by_offset:
                            cr.execute(
                                "UPDATE lcs_event_order SET time_slot_id=%s WHERE id=%s",
                                (slots_by_offset[off], eo.id),
                            )

                seeded += 1
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                'lcs_crm_catering slot migration: SO %s (%s) skipped: %s',
                so.name, so.id, exc,
            )
    _logger.info(
        'lcs_crm_catering slot migration: %d/%d SOs seeded with time slots',
        seeded, len(sos),
    )
