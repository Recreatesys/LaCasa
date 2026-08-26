"""C12 (client comment, slide 12): drop the 💡 set-recommendation note lines.

action_expand_sets no longer creates them, but quotations expanded before
this version still carry one line_note per set, and it renders on the
customer's quotation PDF.

Scope is deliberately limited to DRAFT / SENT orders. A confirmed order is a
document the customer has already agreed to, and silently deleting a line
from it — even a display-only one — rewrites an agreed record. Confirmed
orders lose the note the next time someone runs "Reload Sets", which already
sweeps 💡 lines.
"""


def migrate(cr, version):
    cr.execute(
        """
        DELETE FROM sale_order_line sol
              USING sale_order so
              WHERE sol.order_id = so.id
                AND so.state IN ('draft', 'sent')
                AND sol.display_type = 'line_note'
                AND sol.name LIKE %s
        """,
        ('💡%',),
    )
