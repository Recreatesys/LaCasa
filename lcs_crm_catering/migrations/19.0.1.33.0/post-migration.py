"""Point the SO and Invoice "Send by Email" templates at the LCS reports.

The standard templates (sale.email_template_edi_sale,
account.email_template_edi_invoice) are marked noupdate=t in ir.model.data,
so an XML data file with <field name="report_template_ids"> is silently
ignored. Force the write here so the "LCS Quotation" / "LCS Invoice"
report is the sole attachment on Send by Email.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mapping = [
        ('sale.email_template_edi_sale',       'lcs_crm_catering.action_report_quotation_lcs'),
        ('account.email_template_edi_invoice', 'lcs_crm_catering.action_report_invoice_lcs'),
    ]
    for template_xmlid, report_xmlid in mapping:
        template = env.ref(template_xmlid, raise_if_not_found=False)
        report = env.ref(report_xmlid, raise_if_not_found=False)
        if template and report:
            template.write({'report_template_ids': [(6, 0, [report.id])]})
