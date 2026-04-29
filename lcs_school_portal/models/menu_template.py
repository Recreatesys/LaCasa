from odoo import fields, models

WEEKDAY_SELECTION = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class LcsMenuTemplate(models.Model):
    _name = 'lcs.menu.template'
    _description = 'Menu Weekly Template'
    _order = 'school_id, class_company_id, name'

    name = fields.Char(string='Template Name', required=True, translate=True)
    school_id = fields.Many2one(
        'lcs.school', string='School', required=True, index=True, ondelete='cascade',
    )
    class_company_id = fields.Many2one(
        'res.company', string='Class',
        domain="[('school_id', '=', school_id)]",
        help='Leave empty for school-wide template. Class-specific template overrides school-wide.',
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Note')

    line_ids = fields.One2many(
        'lcs.menu.template.line', 'template_id', string='Items',
    )

    line_count = fields.Integer(compute='_compute_line_count')

    def _compute_line_count(self):
        for tpl in self:
            tpl.line_count = len(tpl.line_ids)


class LcsMenuTemplateLine(models.Model):
    _name = 'lcs.menu.template.line'
    _description = 'Menu Template Line'
    _order = 'template_id, weekday, sequence'

    template_id = fields.Many2one(
        'lcs.menu.template', string='Template', required=True,
        ondelete='cascade', index=True,
    )
    weekday = fields.Selection(
        WEEKDAY_SELECTION, string='Weekday', required=True, index=True,
    )
    item_id = fields.Many2one(
        'lcs.menu.item', string='Item', required=True, ondelete='restrict',
    )
    sequence = fields.Integer(default=10)

    school_id = fields.Many2one(
        related='template_id.school_id', store=True, index=True,
    )
    class_company_id = fields.Many2one(
        related='template_id.class_company_id', store=True, index=True,
    )

    _sql_constraints = [
        ('uniq_template_weekday_item', 'unique(template_id, weekday, item_id)',
         'The same item cannot appear twice on the same weekday in a template.'),
    ]
