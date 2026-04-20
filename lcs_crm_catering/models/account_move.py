from odoo import fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
)
from odoo.addons.lcs_crm_catering.models.sale_order import PAYMENT_METHOD_SELECTION


class AccountMove(models.Model):
    _inherit = 'account.move'

    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    attention_to_id = fields.Many2one(
        'res.partner',
        string='Attention To',
    )
    call_van = fields.Char(string='Call Van')
    delivery_time = fields.Float(string='Delivery Time')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    payment_method = fields.Selection(PAYMENT_METHOD_SELECTION, string='Payment Method')
