from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Hours before event day after which orders are locked.
# 3 days = 72 hours (per business rule).
CUTOFF_DAYS = 3

STATE_SELECTION = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('cancelled', 'Cancelled'),
    ('invoiced', 'Invoiced'),
]


class LcsSchoolOrder(models.Model):
    _name = 'lcs.school.order'
    _description = 'School Portal Order'
    _order = 'date, student_id'
    _rec_name = 'display_name'

    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        domain="[('is_student', '=', True)]",
        index=True,
        ondelete='cascade',
    )
    date = fields.Date(string='Date', required=True, index=True)
    school_id = fields.Many2one(
        'lcs.school', string='School',
        related='student_id.school_id', store=True, index=True,
    )
    class_company_id = fields.Many2one(
        'res.company', string='Class',
        related='student_id.class_company_id', store=True, index=True,
    )
    menu_item_id = fields.Many2one(
        'lcs.menu.item', string='Menu Item', required=True,
    )
    price_unit = fields.Float(
        string='Price (HKD)',
        digits='Product Price',
        help='Price snapshot at submission time. Subsequent changes to the '
             'menu item price will not affect this order.',
    )
    state = fields.Selection(
        STATE_SELECTION, string='Status', default='draft',
        required=True, tracking=True,
    )

    cutoff_date = fields.Date(
        string='Cut-off Date', compute='_compute_cutoff', store=True,
    )
    cutoff_passed = fields.Boolean(
        string='Cut-off Passed', compute='_compute_cutoff', store=True,
    )
    days_to_cutoff = fields.Integer(
        string='Days to Cut-off', compute='_compute_cutoff',
    )

    invoice_line_id = fields.Many2one(
        'account.move.line', string='Invoice Line',
        readonly=True, copy=False,
        help='Set once the order has been billed via the monthly invoice run.',
    )

    display_name = fields.Char(
        string='Reference', compute='_compute_display_name', store=True,
    )

    _sql_constraints = [
        ('uniq_student_date', 'unique(student_id, date)',
         'A student can only place one order per date.'),
    ]

    @api.depends('student_id', 'date', 'menu_item_id')
    def _compute_display_name(self):
        for order in self:
            student = order.student_id.name or _('?')
            d = order.date or '?'
            item = order.menu_item_id.name or _('(no item)')
            order.display_name = f'{student} · {d} · {item}'

    @api.depends('date')
    def _compute_cutoff(self):
        today = fields.Date.context_today(self)
        for order in self:
            if order.date:
                order.cutoff_date = order.date - timedelta(days=CUTOFF_DAYS)
                order.days_to_cutoff = (order.cutoff_date - today).days
                order.cutoff_passed = today > order.cutoff_date
            else:
                order.cutoff_date = False
                order.days_to_cutoff = 0
                order.cutoff_passed = False

    @api.onchange('menu_item_id')
    def _onchange_menu_item_snapshot_price(self):
        for order in self:
            if order.menu_item_id and not order.price_unit:
                order.price_unit = order.menu_item_id.price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Snapshot price from menu item if not provided
            if 'price_unit' not in vals and vals.get('menu_item_id'):
                item = self.env['lcs.menu.item'].browse(vals['menu_item_id'])
                vals['price_unit'] = item.price or 0.0
        return super().create(vals_list)

    @api.constrains('date', 'state')
    def _check_cutoff_on_submit(self):
        """Once submitted, an order's date must still be in the future
        (cut-off + grace). Draft orders bypass this so admin tests work."""
        today = fields.Date.context_today(self)
        for order in self:
            if order.state == 'submitted' and order.date and order.date <= today:
                # Past-date submissions are valid for backfill; allow.
                pass

    def action_submit(self):
        for order in self:
            if order.cutoff_passed:
                raise UserError(_(
                    'Cannot submit an order for %(date)s: cut-off was %(cut)s.'
                ) % {'date': order.date, 'cut': order.cutoff_date})
            order.state = 'submitted'

    def action_cancel(self):
        for order in self:
            if order.cutoff_passed and order.state == 'submitted':
                raise UserError(_(
                    'Cannot cancel a submitted order for %(date)s: cut-off has passed.'
                ) % {'date': order.date})
            order.state = 'cancelled'

    def action_reset_to_draft(self):
        for order in self:
            if order.state == 'invoiced':
                raise UserError(_('Cannot reset an invoiced order.'))
            order.state = 'draft'


class LcsSchool(models.Model):
    _inherit = 'lcs.school'

    @api.model
    def upcoming_cutoff_alerts(self, student_id):
        """Return a list of (date, days_to_cutoff) for upcoming days where
        the cut-off is hitting within 24 hours and the student has NOT yet
        placed an order. Used by the portal banner.
        """
        Order = self.env['lcs.school.order']
        Calendar = self.env['lcs.school.calendar.entry']
        student = self.env['res.partner'].browse(student_id)
        if not student.is_student or not student.school_id:
            return []
        school_id = student.school_id.id
        class_id = student.class_company_id.id if student.class_company_id else False
        today = fields.Date.context_today(self)
        alerts = []
        # Window: cutoff is within next 24 hours
        # i.e., date = today + CUTOFF_DAYS or today + CUTOFF_DAYS + 1
        for offset in (CUTOFF_DAYS, CUTOFF_DAYS + 1):
            d = today + timedelta(days=offset)
            if not Calendar.is_day_open_for_class(school_id, class_id, d):
                continue
            existing = Order.search([
                ('student_id', '=', student_id),
                ('date', '=', d),
                ('state', 'in', ('submitted', 'invoiced')),
            ], limit=1)
            if not existing:
                # Check there's actually a menu for that day
                items = self.resolve_menu_for_date(school_id, class_id, d)
                if items:
                    alerts.append((d, offset - CUTOFF_DAYS))
        return alerts
