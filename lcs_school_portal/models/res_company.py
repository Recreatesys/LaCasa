from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    school_id = fields.Many2one(
        'lcs.school',
        string='School',
        help='School this class belongs to.',
        index=True,
    )
    is_class = fields.Boolean(
        string='Is Class',
        compute='_compute_is_class',
        store=True,
        help='True if this company represents a school class.',
    )

    def _compute_is_class(self):
        for company in self:
            company.is_class = bool(company.school_id)
