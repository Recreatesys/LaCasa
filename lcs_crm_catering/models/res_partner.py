from odoo import fields, models

from odoo.addons.lcs_crm_catering.models.crm_lead import CLIENT_TYPE_SELECTION


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shortname = fields.Char(
        string='Short Name',
        help='Used in invoice/quotation reference numbers, e.g. QM for Queen Mary Hospital',
    )

    # C01 (client comment, slide 1): "We should be able to define this client
    # type when we create a new client. No need to ask here." The customer
    # record is now the source of truth; opportunities and quotations pre-fill
    # from it rather than asking every time.
    client_type = fields.Selection(
        CLIENT_TYPE_SELECTION, string='Client Type',
        help='Corporate / Private / Organization / Partner. Pre-fills the '
             'Client Type on this customer\'s opportunities and quotations.',
    )

    def _lcs_resolve_client_type(self):
        """This partner's client type, falling back to its parent company.

        A quotation is often addressed to a contact under a company; the type
        belongs to the company, so a blank contact inherits it.
        """
        self.ensure_one()
        return self.client_type or self.commercial_partner_id.client_type
