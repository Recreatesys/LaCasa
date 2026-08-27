"""C05a (client comment, slide 5): remap the two service types the client dropped.

The client's Service Type list has no "Sit-down Menu" and no bare "Event", so
both keys leave SERVICE_TYPE_SELECTION. Rows still holding them have to be
remapped BEFORE Odoo reconciles ir.model.fields.selection during the upgrade —
hence pre-migration, not post.

Both are remapped to the new 'event_banquet':

  sit_down_menu  31 Sales Orders / 31 Event Orders. 27 of the 31 already carry
                 delivery_type='event', so these are plated sit-down events —
                 a banquet in the client's new vocabulary.
  event           2 Sales Orders, both 2024 legacy imports named
                 *_LacasaE_GateHK whose only order line is a placeholder
                 "Event — 2024-01-25". No dish detail to classify them more
                 precisely; 'event_banquet' at least keeps them as events.

Everything else keeps its key. 'buffet' and 'cocktail' are only relabelled
("Event – Buffet" / "Event – Cocktail"), as are 'utensil' → "Utensil Rental"
and 'waiter_service' → "Staffing", so no data moves for those.

delivery_type needs nothing: all three existing keys survive the reorder and
the three new ones (simple_setup_round, simple_setup_one, self_pickup) are
purely additive.
"""

import logging

_logger = logging.getLogger(__name__)

# NB: deliberately explicit. product_template also has a service_type column,
# but that is standard Odoo's ('manual' / 'timesheet') and must not be touched.
TABLES = (
    'crm_lead',
    'sale_order',
    'account_move',
    'lcs_event_order',
    # Stored related copy of lcs_event_order.service_type — a raw UPDATE on the
    # parent does not recompute it, so it is remapped alongside.
    'lcs_event_order_line',
)

RETIRED = ('sit_down_menu', 'event')
REPLACEMENT = 'event_banquet'


def migrate(cr, version):
    for table in TABLES:
        cr.execute(
            """
            UPDATE %s
               SET service_type = %%s
             WHERE service_type IN %%s
            """ % table,
            (REPLACEMENT, RETIRED),
        )
        if cr.rowcount:
            _logger.info(
                'C05a: remapped %s row(s) in %s from %s to %r',
                cr.rowcount, table, RETIRED, REPLACEMENT,
            )
