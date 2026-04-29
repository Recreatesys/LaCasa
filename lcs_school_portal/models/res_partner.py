from odoo import api, fields, models

DIET_PREFERENCE_SELECTION = [
    ('combo', 'Combo (no restriction)'),
    ('vegetarian', 'Vegetarian'),
    ('vegan', 'Vegan'),
    ('no_pork', 'No Pork'),
    ('no_beef', 'No Beef'),
    ('no_pork_no_beef', 'No Pork or Beef'),
    ('halal', 'Halal'),
    ('others', 'Others'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_student = fields.Boolean(
        string='Is Student', default=False, index=True,
    )
    chinese_name = fields.Char(string='Chinese Name')
    student_no = fields.Char(string='Student No.', index=True)
    guardian_name = fields.Char(string='Parent Name')
    guardian_phone = fields.Char(string='Parent Phone')

    allergy_ids = fields.Many2many(
        'lcs.allergy', 'res_partner_allergy_rel', 'partner_id', 'allergy_id',
        string='Allergies',
    )
    diet_preference = fields.Selection(
        DIET_PREFERENCE_SELECTION, string='Diet Preference', default='combo',
    )

    class_company_id = fields.Many2one(
        'res.company',
        string='Class',
        domain="[('is_class', '=', True)]",
        help='Class (Odoo company) this student belongs to.',
        index=True,
    )
    school_id = fields.Many2one(
        'lcs.school',
        string='School',
        related='class_company_id.school_id',
        store=True,
        index=True,
    )

    @api.onchange('class_company_id')
    def _onchange_class_company_id(self):
        for partner in self:
            if partner.class_company_id:
                partner.company_id = partner.class_company_id
                partner.parent_id = partner.class_company_id.partner_id
