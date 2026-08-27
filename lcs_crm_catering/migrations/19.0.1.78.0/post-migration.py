"""C01 (client comment, slide 1): seed res.partner.client_type from history.

The customer record is now the source of truth for Client Type, but no
existing customer has one — the value has only ever been captured per
opportunity and per quotation. Without a back-fill, every one of the 876
customers who already have classified orders would still be asked on their
next opportunity, which is the exact loop slide 1 complains about.

Each customer takes the client_type used most often across their own Sales
Orders. 46 customers have been classified inconsistently over time (a
Corporate order here, a Partner order there); for those the most frequent
value wins, and the most recent order breaks a tie. Nothing is overwritten —
only customers with no client_type are touched — so anyone the team has
already classified by hand keeps that value.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        WITH ranked AS (
            SELECT partner_id,
                   client_type,
                   row_number() OVER (
                       PARTITION BY partner_id
                       ORDER BY count(*) DESC, max(date_order) DESC
                   ) AS rn
              FROM sale_order
             WHERE client_type IS NOT NULL
               AND partner_id IS NOT NULL
             GROUP BY partner_id, client_type
        )
        UPDATE res_partner p
           SET client_type = r.client_type
          FROM ranked r
         WHERE p.id = r.partner_id
           AND r.rn = 1
           AND p.client_type IS NULL
        """
    )
    _logger.info('C01: seeded client_type on %s customer(s)', cr.rowcount)
