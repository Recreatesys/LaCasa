from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CombinedInvoiceWizard(models.TransientModel):
    _name = 'lcs.combined.invoice.wizard'
    _description = 'Consolidated Billing Invoice Wizard'

    sale_order_ids = fields.Many2many(
        'sale.order', string='Sales Orders', required=True,
    )
    payment_type = fields.Selection(
        [
            ('full', 'Full Payment'),
            ('percentage', 'Percentage of Total'),
            ('amount', 'Fixed Amount'),
        ],
        string='Payment Type', required=True, default='full',
    )
    percentage = fields.Float(
        string='Percentage (%)', default=50.0,
        help='0-100. Applied to the sum of all selected orders.',
    )
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id',
    )
    total_amount = fields.Monetary(
        string='Selected Orders Total',
        compute='_compute_total_amount',
        currency_field='currency_id',
    )
    billed_amount = fields.Monetary(
        string='Amount to Bill Now',
        compute='_compute_billed_amount',
        currency_field='currency_id',
    )

    @api.depends('sale_order_ids')
    def _compute_currency_id(self):
        for wiz in self:
            wiz.currency_id = wiz.sale_order_ids[:1].currency_id \
                or wiz.env.company.currency_id

    @api.depends('sale_order_ids')
    def _compute_total_amount(self):
        for wiz in self:
            wiz.total_amount = sum(wiz.sale_order_ids.mapped('amount_total'))

    @api.depends('payment_type', 'percentage', 'amount', 'total_amount')
    def _compute_billed_amount(self):
        for wiz in self:
            if wiz.payment_type == 'full':
                wiz.billed_amount = wiz.total_amount
            elif wiz.payment_type == 'percentage':
                wiz.billed_amount = wiz.total_amount * (wiz.percentage or 0.0) / 100.0
            elif wiz.payment_type == 'amount':
                wiz.billed_amount = wiz.amount or 0.0
            else:
                wiz.billed_amount = 0.0

    def action_create_invoice(self):
        self.ensure_one()
        if not self.sale_order_ids:
            raise UserError(_('No Sales Orders selected.'))
        if self.payment_type == 'percentage':
            if not (0 < self.percentage <= 100):
                raise UserError(_('Percentage must be between 0 and 100.'))
        if self.payment_type == 'amount':
            if self.amount <= 0:
                raise UserError(_('Amount must be greater than 0.'))
            if self.amount > self.total_amount:
                raise UserError(_(
                    'Amount %(a)s exceeds the total of the selected orders '
                    '(%(t)s).',
                    a=self.amount, t=self.total_amount,
                ))
        return self.sale_order_ids.action_create_combined_invoice(
            payment_type=self.payment_type,
            percentage=self.percentage,
            amount=self.amount,
        )
