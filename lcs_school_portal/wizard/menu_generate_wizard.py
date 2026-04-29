from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LcsMenuGenerateWizard(models.TransientModel):
    _name = 'lcs.menu.generate.wizard'
    _description = 'Generate Menu Days from Template'

    template_id = fields.Many2one(
        'lcs.menu.template', string='Template', required=True,
    )
    school_id = fields.Many2one(
        'lcs.school', related='template_id.school_id', readonly=True,
    )
    class_company_id = fields.Many2one(
        'res.company', related='template_id.class_company_id', readonly=True,
    )
    date_from = fields.Date(string='From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='To', required=True)
    skip_closed_days = fields.Boolean(
        string='Skip Closed Days',
        default=True,
        help='Skip days that are closed (weekends, holidays, exam days) according to the school calendar.',
    )
    overwrite_existing = fields.Boolean(
        string='Overwrite Existing',
        default=False,
        help='If checked, replace items on existing menu days. Otherwise, skip them.',
    )

    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from and not self.date_to:
            self.date_to = self.date_from + timedelta(days=27)

    def action_generate(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('"To" date must be on or after "From" date.'))
        if not self.template_id.line_ids:
            raise UserError(_('The selected template has no items.'))

        Day = self.env['lcs.menu.day']
        Calendar = self.env['lcs.school.calendar.entry']

        # Pre-build {weekday: [item_ids]} for fast lookup
        items_by_weekday = {}
        for line in self.template_id.line_ids:
            items_by_weekday.setdefault(line.weekday, []).append(line.item_id.id)

        created, updated, skipped = 0, 0, 0
        d = self.date_from
        while d <= self.date_to:
            weekday = str(d.weekday())
            item_ids = items_by_weekday.get(weekday, [])

            if not item_ids:
                d += timedelta(days=1)
                continue

            if self.skip_closed_days:
                is_open = Calendar.is_day_open_for_class(
                    self.school_id.id,
                    self.class_company_id.id if self.class_company_id else False,
                    d,
                )
                if not is_open:
                    d += timedelta(days=1)
                    continue

            existing = Day.search([
                ('date', '=', d),
                ('school_id', '=', self.school_id.id),
                ('class_company_id', '=', self.class_company_id.id if self.class_company_id else False),
            ], limit=1)

            if existing:
                if self.overwrite_existing:
                    existing.item_ids = [(6, 0, item_ids)]
                    updated += 1
                else:
                    skipped += 1
            else:
                Day.create({
                    'date': d,
                    'school_id': self.school_id.id,
                    'class_company_id': self.class_company_id.id if self.class_company_id else False,
                    'item_ids': [(6, 0, item_ids)],
                })
                created += 1

            d += timedelta(days=1)

        msg = _('Created: %(c)s · Updated: %(u)s · Skipped: %(s)s') % {
            'c': created, 'u': updated, 's': skipped,
        }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Generate Menu Days'),
                'message': msg,
                'sticky': False,
                'type': 'success' if (created or updated) else 'warning',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
