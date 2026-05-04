from odoo import fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
    SETUP_TYPE_SELECTION,
)
from odoo.addons.lcs_crm_catering.models.sale_order import CALL_VAN_SELECTION, PAYMENT_METHOD_SELECTION


class AccountMove(models.Model):
    _inherit = 'account.move'

    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    attention_to_id = fields.Many2one(
        'res.partner',
        string='Attention To',
    )
    call_van = fields.Selection(CALL_VAN_SELECTION, string='Call Van')
    delivery_time = fields.Float(string='Delivery Time')
    event_date = fields.Date(string='Event / Delivery Date')
    event_street = fields.Char(string='Delivery Street')
    event_street2 = fields.Char(string='Delivery Street 2')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    payment_method = fields.Selection(PAYMENT_METHOD_SELECTION, string='Payment Method')
    no_logo = fields.Boolean(
        string='No Logo',
        help='Hide LaCasa branding from packaging / signage (white-label).',
    )
    setup_type = fields.Selection(
        SETUP_TYPE_SELECTION, string='Setup Type',
    )
    is_wedding = fields.Boolean(
        string='Wedding-related',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'call_van' in vals and not self.env.context.get('skip_call_van_sync'):
            for inv in self:
                sos = inv.line_ids.sale_line_ids.order_id
                sos = sos.filtered(lambda s: s.call_van != vals['call_van'])
                if sos:
                    sos.with_context(skip_call_van_sync=True).write({'call_van': vals['call_van']})
        return res
