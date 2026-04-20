from odoo import api, fields, models


BRAND_SELECTION = [
    ('lacasa', 'Lacasa'),
    ('mr_mix', 'Mr Mix'),
    ('meerkat', 'Meerkat'),
]

CLIENT_TYPE_SELECTION = [
    ('corporate', 'Corporate'),
    ('private', 'Private'),
    ('organization', 'Organization'),
]

SERVICE_FORMAT_SELECTION = [
    ('food_delivery', 'Food Delivery'),
    ('event_catering', 'Event Catering'),
]

SERVICE_TYPE_SELECTION = [
    ('canapes', 'Canapes'),
    ('party_food', 'Party Food'),
    ('meal_box', 'Meal Box'),
    ('buffet', 'Buffet'),
    ('cocktail', 'Cocktail'),
    ('wedding_buffet', 'Wedding Buffet'),
    ('wedding_cocktail', 'Wedding Cocktail'),
    ('breakfast_refreshment', 'Breakfast / Refreshment Break'),
    ('sit_down_menu', 'Sit-down Menu'),
    ('utensil', 'Utensil'),
    ('waiter_service', 'Waiter Service'),
    ('oem', 'OEM'),
    ('school_meal', 'School Meal'),
    ('food_tasting', 'Food Tasting'),
    ('staff_meal', 'Staff Meal'),
]

DELIVERY_TYPE_SELECTION = [
    ('event', 'Event'),
    ('drop_off_pickup', 'Drop-off (Pick-up from Driver)'),
    ('drop_off_door', 'Drop-off (Door to door)'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Event / Delivery fields
    event_date = fields.Date(string='Event / Delivery Date')
    event_street = fields.Char(string='Street')
    event_street2 = fields.Char(string='Street 2')
    event_country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.hk', raise_if_not_found=False),
    )

    # Catering fields
    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    client_type = fields.Selection(CLIENT_TYPE_SELECTION, string='Client Type')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
