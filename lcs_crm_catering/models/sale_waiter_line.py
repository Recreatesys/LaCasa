from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleWaiterLine(models.Model):
    _name = 'lcs.sale.waiter.line'
    _description = 'Sales Order Waiter Assignment'
    _order = 'start_datetime, employee_id'

    order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        domain="[('job_id.name', '=', 'Event Staff')]",
    )
    role = fields.Char(
        string='Role',
        related='employee_id.job_title',
        readonly=True,
        store=True,
    )
    start_datetime = fields.Datetime(string='Start Time', required=True)
    end_datetime = fields.Datetime(string='End Time', required=True)
    hours = fields.Float(
        string='Hours of Service',
        compute='_compute_hours',
        store=True,
        digits=(8, 2),
    )

    order_state = fields.Selection(
        related='order_id.state', store=True, readonly=True,
    )

    @api.depends('start_datetime', 'end_datetime')
    def _compute_hours(self):
        for line in self:
            if line.start_datetime and line.end_datetime and \
               line.end_datetime > line.start_datetime:
                delta = line.end_datetime - line.start_datetime
                line.hours = delta.total_seconds() / 3600.0
            else:
                line.hours = 0.0

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for line in self:
            if line.start_datetime and line.end_datetime \
                    and line.end_datetime <= line.start_datetime:
                raise ValidationError(_('End Time must be after Start Time.'))

    @api.constrains('employee_id', 'start_datetime', 'end_datetime', 'order_state')
    def _check_no_double_booking(self):
        """Once an SO is confirmed (state in sale/done), an employee cannot
        have overlapping waiter lines on another confirmed SO."""
        for line in self:
            if line.order_id.state not in ('sale', 'done'):
                continue
            if not (line.start_datetime and line.end_datetime
                    and line.employee_id):
                continue
            conflict = self.search([
                ('id', '!=', line.id),
                ('employee_id', '=', line.employee_id.id),
                ('order_id.state', 'in', ('sale', 'done')),
                ('start_datetime', '<', line.end_datetime),
                ('end_datetime', '>', line.start_datetime),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    'Employee %(emp)s is already booked on %(so)s '
                    'from %(start)s to %(end)s.'
                ) % {
                    'emp': line.employee_id.name,
                    'so': conflict.order_id.name,
                    'start': conflict.start_datetime,
                    'end': conflict.end_datetime,
                })

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.order_id._sync_waiter_service_line()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self.mapped('order_id')._sync_waiter_service_line()
        return res

    def unlink(self):
        orders = self.mapped('order_id')
        res = super().unlink()
        orders._sync_waiter_service_line()
        return res
