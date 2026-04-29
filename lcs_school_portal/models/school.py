from odoo import fields, models


class LcsSchool(models.Model):
    _name = 'lcs.school'
    _description = 'School'
    _order = 'name'

    name = fields.Char(string='School Name', required=True, translate=True)
    short_code = fields.Char(string='Short Code', help='Optional short code, e.g. LTF for 林大輝中學')
    active = fields.Boolean(default=True)
    company_ids = fields.One2many(
        'res.company', 'school_id', string='Classes',
    )
    student_count = fields.Integer(
        string='# Students', compute='_compute_student_count',
    )

    def _compute_student_count(self):
        Partner = self.env['res.partner']
        for school in self:
            school.student_count = Partner.search_count([
                ('is_student', '=', True),
                ('school_id', '=', school.id),
            ])
