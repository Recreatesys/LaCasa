"""C25: re-derive kitchen units that fell back to the generic product UoM.

Not one of the 579 products has kitchen_uom filled in, so every Event Order
line without a ratio tier behind it took product.uom_id.name and came out as
"45 Units". Lines that DO have a tier were always right ("2 x 1/2 GN tray")
and are left alone.

Only food lines whose source Sales Order line carries a resolved set unit are
touched, and only where the current value is empty or the generic UoM name —
a kitchen unit somebody typed by hand is preserved.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    EOLine = env['lcs.event.order.line']

    generic_names = set(
        env['uom.uom'].with_context(active_test=False).search([]).mapped('name')
    )

    lines = EOLine.search([
        ('is_food_item', '=', True),
        ('sale_line_id', '!=', False),
    ])
    fixed = 0
    for line in lines:
        current = (line.kitchen_uom or '').strip()
        if current and current not in generic_names:
            continue  # a real unit, possibly hand-entered — leave it
        sol = line.sale_line_id
        if sol.eo_qty and sol.eo_unit:
            continue  # ratio tier already gave the right answer
        new_unit = EOLine._lcs_source_kitchen_unit(sol)
        if new_unit and new_unit != current:
            line.kitchen_uom = new_unit
            fixed += 1

    _logger.info(
        'C25: re-derived the kitchen unit on %s of %s food EO line(s)',
        fixed, len(lines),
    )
