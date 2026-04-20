from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    shortname = fields.Char(
        string='Short Name',
        help='Used in invoice/quotation reference numbers, e.g. QM for Queen Mary Hospital',
    )
