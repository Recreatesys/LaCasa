from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DAY_TYPE_SELECTION = [
    ('public_holiday', 'Public Holiday'),
    ('school_holiday', 'School Holiday'),
    ('exam', 'Exam Day'),
    ('special_open', 'Special Open Day'),
]

# day_type -> (is_open, color index for kanban/calendar)
# Color conventions (Odoo color picker, 1-11):
#   1=red, 2=orange, 3=yellow, 4=light blue, 5=dark purple,
#   6=salmon, 7=teal, 8=blue, 9=fuchsia, 10=green, 11=violet
DAY_TYPE_META = {
    'public_holiday': (False, 1),    # red
    'school_holiday': (False, 9),    # fuchsia
    'exam': (False, 2),              # orange
    'special_open': (True, 10),      # green
}


class SchoolCalendarEntry(models.Model):
    _name = 'lcs.school.calendar.entry'
    _description = 'School Calendar Entry'
    _order = 'date, school_id, class_company_id'

    name = fields.Char(string='Title', required=True, translate=True)
    date = fields.Date(string='Date', required=True, index=True)
    date_end = fields.Date(
        string='End Date',
        help='Optional. If set, this entry covers a date range (inclusive).',
    )
    school_id = fields.Many2one(
        'lcs.school', string='School', required=True, index=True, ondelete='cascade',
    )
    class_company_id = fields.Many2one(
        'res.company', string='Class',
        domain="[('school_id', '=', school_id)]",
        help='Leave empty to apply to the whole school. '
             'A class-level entry overrides a school-level entry on the same day.',
        index=True,
    )
    day_type = fields.Selection(
        DAY_TYPE_SELECTION,
        string='Type',
        required=True,
        default='school_holiday',
    )
    is_open = fields.Boolean(
        string='Open for Orders',
        compute='_compute_is_open_color', store=True,
    )
    color = fields.Integer(
        string='Color',
        compute='_compute_is_open_color', store=True,
    )
    note = fields.Text(string='Note')

    _sql_constraints = [
        ('date_range_check', 'CHECK (date_end IS NULL OR date_end >= date)',
         'End Date must be on or after the start Date.'),
    ]

    @api.depends('day_type')
    def _compute_is_open_color(self):
        for entry in self:
            is_open, color = DAY_TYPE_META.get(entry.day_type, (True, 0))
            entry.is_open = is_open
            entry.color = color

    @api.model
    def is_day_open_for_class(self, school_id, class_company_id, check_date):
        """Resolve open/closed status for a given date and class.

        Resolution order:
          1. Class-level calendar entry covering the date (if class_company_id set)
          2. School-level calendar entry covering the date
          3. Default: weekdays open, Sat/Sun closed
        """
        domain = [
            ('school_id', '=', school_id),
            ('date', '<=', check_date),
            '|', ('date_end', '=', False), ('date_end', '>=', check_date),
        ]
        if class_company_id:
            entry = self.search(
                domain + [('class_company_id', '=', class_company_id)], limit=1,
            )
            if entry:
                return entry.is_open

        entry = self.search(
            domain + [('class_company_id', '=', False)], limit=1,
        )
        if entry:
            return entry.is_open

        # Default: Mon-Fri (0-4) open, Sat-Sun closed
        return check_date.weekday() < 5


class LcsSchool(models.Model):
    _inherit = 'lcs.school'

    calendar_entry_ids = fields.One2many(
        'lcs.school.calendar.entry', 'school_id', string='Calendar Entries',
    )
    calendar_entry_count = fields.Integer(
        string='# Calendar Entries', compute='_compute_calendar_entry_count',
    )

    def _compute_calendar_entry_count(self):
        Entry = self.env['lcs.school.calendar.entry']
        for school in self:
            school.calendar_entry_count = Entry.search_count([
                ('school_id', '=', school.id),
            ])

    def action_view_calendar(self):
        self.ensure_one()
        return {
            'name': _('Calendar — %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'lcs.school.calendar.entry',
            'view_mode': 'calendar,list,form',
            'domain': [('school_id', '=', self.id)],
            'context': {'default_school_id': self.id},
        }

    def action_load_hk_public_holidays(self):
        """Bulk-add HK public holidays as 'public_holiday' entries.

        Loads holidays for the current year and next year using the
        python-holidays library. Skips dates already present at school level.
        """
        try:
            import holidays as holidays_lib
        except ImportError:
            raise UserError(_(
                'The python-holidays library is not installed on the server. '
                'Install with: pip install holidays'
            ))

        Entry = self.env['lcs.school.calendar.entry']
        today = fields.Date.context_today(self)
        years = [today.year, today.year + 1]

        for school in self:
            existing = set(
                d for d in Entry.search([
                    ('school_id', '=', school.id),
                    ('class_company_id', '=', False),
                    ('date', '>=', date(years[0], 1, 1)),
                    ('date', '<=', date(years[-1], 12, 31)),
                ]).mapped('date')
            )

            hk = holidays_lib.HK(years=years)
            new_vals = []
            for d, name in sorted(hk.items()):
                if d in existing:
                    continue
                new_vals.append({
                    'name': name,
                    'date': d,
                    'school_id': school.id,
                    'day_type': 'public_holiday',
                })

            if new_vals:
                Entry.create(new_vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('HK Public Holidays loaded'),
                'message': _('Loaded HK public holidays for %s. Existing entries were skipped.')
                            % ', '.join(str(y) for y in years),
                'sticky': False,
                'type': 'success',
            },
        }
