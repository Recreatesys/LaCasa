"""Restore LCS A4 paperformat side margins to 12mm.

19.0.1.57.0 dropped them to 10mm, which combined with the aggressive
CSS reset made the invoice PDF's edge content clip / overflow. Put
side margins back to 12mm; the CSS reset now only affects vertical
padding so horizontal breathing room comes from the paperformat.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pf = env.ref('lcs_crm_catering.paperformat_lcs_a4', raise_if_not_found=False)
    if not pf:
        return
    pf.write({
        'margin_top': 5,
        'margin_bottom': 10,
        'margin_left': 12,
        'margin_right': 12,
    })
