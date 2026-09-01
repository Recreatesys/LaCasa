"""Finish what 19.0.2.28.0 started: push the corrected units onto the EO lines.

That migration re-pointed the ratio tiers and refreshed eo_qty / eo_unit on
527 sale order lines, but its final SQL reported 0 Event Order lines updated.
The writes were still in the ORM cache; raw SQL does not see un-flushed
changes, so the UPDATE matched nothing. 28.0 now flushes, and this repairs the
databases where it already ran.

Kitchen fields only. Nothing quoted or billed is touched.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE lcs_event_order_line l
           SET kitchen_qty = sol.eo_qty,
               kitchen_uom = sol.eo_unit
          FROM sale_order_line sol, lcs_event_order eo
         WHERE sol.id = l.sale_line_id
           AND eo.id = l.order_id
           AND coalesce(eo.payment_status, '') <> 'cancelled'
           AND coalesce(sol.eo_qty, 0) <> 0
           AND coalesce(sol.eo_unit, '') <> ''
           AND (l.kitchen_qty IS DISTINCT FROM sol.eo_qty
                OR coalesce(l.kitchen_uom, '')
                   IS DISTINCT FROM coalesce(sol.eo_unit, ''))
        """
    )
    _logger.info('C25: pushed corrected units onto %s Event Order line(s)',
                 cr.rowcount)
