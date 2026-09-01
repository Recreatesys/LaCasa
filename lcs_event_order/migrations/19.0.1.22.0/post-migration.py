"""C25: re-derive kitchen units that fell back to the generic product UoM.

Not one of the 579 products has kitchen_uom filled in, so every Event Order
line without a ratio tier behind it took product.uom_id.name and came out as
"45 Units". Lines that DO have a tier were always right ("2 x 1/2 GN tray")
and are left alone.

Written as SQL on purpose. sale_order_line.set_unit / eo_qty / eo_unit belong
to lcs_product_catalog, which loads AFTER lcs_event_order — they are absent
from the registry at this point, which is why the model code guards every
access with hasattr(). The columns themselves exist in the database, so SQL
can read them safely.

Only rows whose current value is empty or the generic "Units" are touched, so
a kitchen unit somebody typed by hand is preserved.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE lcs_event_order_line l
           SET kitchen_uom = CASE
                   WHEN sol.set_unit = 'Per piece' THEN 'pcs'
                   ELSE sol.set_unit
               END
          FROM sale_order_line sol
         WHERE sol.id = l.sale_line_id
           AND l.is_food_item IS TRUE
           AND coalesce(sol.set_unit, '') <> ''
           -- a ratio tier already produced the right answer here
           AND NOT (coalesce(sol.eo_qty, 0) <> 0
                    AND coalesce(sol.eo_unit, '') <> '')
           AND coalesce(l.kitchen_uom, '') IN ('', 'Units')
        """
    )
    _logger.info('C25: re-derived the kitchen unit on %s EO line(s)', cr.rowcount)
