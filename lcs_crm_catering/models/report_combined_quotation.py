from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import _


class ReportCombinedQuotation(models.AbstractModel):
    """Feeds the Combined LCS Quotation report.

    Why this exists rather than just binding the report to the list view:

    ir.actions.report splits a rendered PDF back into one stream per record,
    matching PDF outlines against res_ids. A combined report emits N+1 bodies
    (one summary cover plus one page per quotation) for N records, so those
    counts never match, and base Odoo falls back to
    _render_qweb_pdf_prepare_streams(res_ids=[res_id]) *per record*
    (odoo/addons/base/models/ir_actions_report.py). Each of those passes
    renders its own cover, so four quotations produced four covers each
    reading "# Quotations: 1" — the report never actually combined anything.

    Base Odoo returns the PDF whole and unsplit when res_ids is empty:

        if has_duplicated_ids or not res_ids:
            return {False: {'stream': pdf_content_stream, ...}}

    So the orders travel in `data` instead of as res_ids, and this model hands
    them to the template as `docs`.
    """
    _name = 'report.lcs_crm_catering.report_combined_quotation_lcs'
    _description = 'Combined LCS Quotation Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        order_ids = (data or {}).get('order_ids') or docids or []
        orders = self.env['sale.order'].browse(order_ids).exists()
        if not orders:
            raise UserError(_('No quotations to combine.'))
        # Chronological reading order for the customer: event date, then time.
        orders = orders.sorted(
            lambda o: (o.event_date or o.date_order.date(),
                       o.event_time_start or 0.0,
                       o.name or '')
        )
        return {
            'doc_ids': orders.ids,
            'doc_model': 'sale.order',
            'docs': orders,
        }
