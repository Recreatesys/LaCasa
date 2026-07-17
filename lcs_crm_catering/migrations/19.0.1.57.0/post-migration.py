"""Tighten LCS A4 paperformat top/bottom margins.

The paperformat data record uses noupdate="1", so XML changes to its
fields are ignored on upgrade. Force-update the DB values here so the
tighter margins take effect for the invoice & quotation reports.
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
        'margin_left': 10,
        'margin_right': 10,
        'header_spacing': 0,
        'header_line': False,
    })
