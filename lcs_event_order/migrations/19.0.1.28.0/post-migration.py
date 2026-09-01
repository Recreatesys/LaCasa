"""Back-fill Driver Status from Call Van.

19.0.1.27.0 turned driver_status into a stored compute on call_van, but Odoo
only computes a stored field for rows that do not already have a value. The
column had been created one version earlier with a default of 'to_assign', so
every one of the 5,528 active Event Orders kept that default and the link to
Call Van appeared to do nothing.

Only rows still sitting at the default are touched, so any status CS has
already advanced by hand is preserved.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE lcs_event_order
           SET driver_status = CASE
                   WHEN coalesce(call_van, '') IN ('', 'preferred_driver')
                       THEN 'to_assign'
                   WHEN call_van IN ('no_need', 'self_pickup',
                                     'self_deliver', 'event_team')
                       THEN 'not_required'
                   ELSE 'assigned'
               END
         WHERE coalesce(driver_status, 'to_assign') = 'to_assign'
        """
    )
    _logger.info('C26a: derived Driver Status on %s Event Order(s)', cr.rowcount)
