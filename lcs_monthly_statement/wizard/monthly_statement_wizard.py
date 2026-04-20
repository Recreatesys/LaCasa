from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class MonthlyStatementWizard(models.TransientModel):
    _name = 'lcs.monthly.statement.wizard'
    _description = 'Monthly Statement Wizard'

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )
    month = fields.Selection(
        [(str(i), date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Month',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Year',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    brand = fields.Selection(
        [('lacasa', 'Lacasa'), ('mr_mix', 'Mr Mix'), ('meerkat', 'Meerkat')],
        string='Brand',
        default='lacasa',
    )

    def action_generate_statement(self):
        """Generate the monthly statement PDF report."""
        self.ensure_one()
        return self.env.ref(
            'lcs_monthly_statement.action_report_monthly_statement'
        ).report_action(self)

    def _get_invoices(self):
        """Get all posted invoices for the customer in the selected month."""
        month_start = date(self.year, int(self.month), 1)
        month_end = month_start + relativedelta(months=1, days=-1)
        return self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', month_start),
            ('invoice_date', '<=', month_end),
        ], order='invoice_date asc')

    def _get_reference_number(self):
        """Generate reference: YYYYMMDD_Brand_CustomerShortname."""
        month_start = date(self.year, int(self.month), 1)
        date_str = month_start.strftime('%Y%m%d')
        brand_str = dict(self._fields['brand'].selection).get(self.brand, 'LaCasa')
        shortname = self.partner_id.shortname or self.partner_id.name
        return '%s_%s_%s' % (date_str, brand_str, shortname)

    def _get_month_year_str(self):
        """Return formatted month/year string, e.g. 'November 2024'."""
        month_name = date(2000, int(self.month), 1).strftime('%B')
        return '%s %s' % (month_name, self.year)
