"""Force the LCS A4 paperformat on standard Odoo report actions we've
re-pointed to our LCS templates.

Root cause of "PDF content pushed to the middle" bug:
- Our LCS templates (report_invoice_lcs_document, report_quotation_lcs_document)
  are rendered by SEVERAL ir.actions.report records: our own
  action_report_invoice_lcs, plus the standard account.account_invoices,
  account.account_invoices_without_payment, and sale.action_report_saleorder
  (redirected to our template names in earlier migrations).
- Only our own action carries paperformat_id = paperformat_lcs_a4.
  The redirected standard actions have paperformat_id = NULL, so they
  fall back to base.paperformat_euro (margin_top=40mm, header_spacing=35mm).
- When a user clicks Print, Odoo picks the standard action; the PDF
  renders with ~50mm of blank at the top of every page.

Fix: stamp paperformat_lcs_a4 onto every action whose report_name
points at our LCS templates.
"""
from odoo import SUPERUSER_ID, api


LCS_REPORT_NAMES = (
    'lcs_crm_catering.report_invoice_lcs_document',
    'lcs_crm_catering.report_quotation_lcs_document',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    pf = env.ref('lcs_crm_catering.paperformat_lcs_a4', raise_if_not_found=False)
    if not pf:
        return
    actions = env['ir.actions.report'].search([
        ('report_name', 'in', LCS_REPORT_NAMES),
    ])
    for action in actions:
        if action.paperformat_id.id != pf.id:
            action.paperformat_id = pf.id
