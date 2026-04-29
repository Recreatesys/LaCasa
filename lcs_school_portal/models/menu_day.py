from odoo import api, fields, models


class LcsMenuDay(models.Model):
    _name = 'lcs.menu.day'
    _description = 'Menu of the Day'
    _order = 'date, school_id, class_company_id'
    _rec_name = 'display_name'

    date = fields.Date(string='Date', required=True, index=True)
    school_id = fields.Many2one(
        'lcs.school', string='School', required=True, index=True, ondelete='cascade',
    )
    class_company_id = fields.Many2one(
        'res.company', string='Class',
        domain="[('school_id', '=', school_id)]",
        help='Leave empty for school-wide. Class-specific menu overrides school-wide on the same date.',
        index=True,
    )
    item_ids = fields.Many2many(
        'lcs.menu.item', 'lcs_menu_day_item_rel', 'menu_day_id', 'item_id',
        string='Items',
    )
    item_count = fields.Integer(compute='_compute_item_count', store=True)
    note = fields.Text(string='Note')

    display_name = fields.Char(compute='_compute_display_name', store=True)
    color = fields.Integer(compute='_compute_color', store=True)

    _sql_constraints = [
        ('uniq_date_school_class',
         'unique(date, school_id, class_company_id)',
         'A menu already exists for this date / school / class combination.'),
    ]

    @api.depends('item_ids')
    def _compute_item_count(self):
        for day in self:
            day.item_count = len(day.item_ids)

    @api.depends('date', 'school_id', 'class_company_id', 'item_count')
    def _compute_display_name(self):
        for day in self:
            scope = day.class_company_id.name if day.class_company_id else (day.school_id.name or '')
            day.display_name = f"{day.date} — {scope} ({day.item_count} items)" if day.date else 'Menu'

    @api.depends('class_company_id', 'item_count')
    def _compute_color(self):
        for day in self:
            if day.class_company_id:
                day.color = 4   # light blue — class-specific
            elif day.item_count:
                day.color = 10  # green — school-wide with items
            else:
                day.color = 0


class LcsSchool(models.Model):
    _inherit = 'lcs.school'

    @api.model
    def resolve_menu_for_date(self, school_id, class_company_id, check_date):
        """Return the recordset of lcs.menu.item available for (school, class, date).

        Resolution priority:
          1. lcs.menu.day for (date, school, class) — most specific override
          2. lcs.menu.day for (date, school, no class) — school-wide override
          3. Active lcs.menu.template for (school, class) — class-specific weekly template
          4. Active lcs.menu.template for (school, no class) — school-wide weekly template
          5. Empty recordset
        """
        Day = self.env['lcs.menu.day']
        Template = self.env['lcs.menu.template']
        weekday = str(check_date.weekday())

        if class_company_id:
            day = Day.search([
                ('date', '=', check_date),
                ('school_id', '=', school_id),
                ('class_company_id', '=', class_company_id),
            ], limit=1)
            if day:
                return day.item_ids

        day = Day.search([
            ('date', '=', check_date),
            ('school_id', '=', school_id),
            ('class_company_id', '=', False),
        ], limit=1)
        if day:
            return day.item_ids

        if class_company_id:
            tpl = Template.search([
                ('active', '=', True),
                ('school_id', '=', school_id),
                ('class_company_id', '=', class_company_id),
            ], limit=1)
            if tpl:
                return tpl.line_ids.filtered(lambda l: l.weekday == weekday).mapped('item_id')

        tpl = Template.search([
            ('active', '=', True),
            ('school_id', '=', school_id),
            ('class_company_id', '=', False),
        ], limit=1)
        if tpl:
            return tpl.line_ids.filtered(lambda l: l.weekday == weekday).mapped('item_id')

        return self.env['lcs.menu.item']
