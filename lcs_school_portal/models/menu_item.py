from odoo import fields, models

from .res_partner import DIET_PREFERENCE_SELECTION


class LcsMenuItem(models.Model):
    _name = 'lcs.menu.item'
    _description = 'Menu Item'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    chinese_name = fields.Char(string='Chinese Name')
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    image = fields.Binary(string='Image', attachment=True)
    price = fields.Float(
        string='Price (HKD)', digits='Product Price', required=True, default=0.0,
    )

    diet_preference = fields.Selection(
        DIET_PREFERENCE_SELECTION,
        string='Diet Tag',
        help='Tag this item with the diet category it satisfies. Used to filter what each student can order.',
    )
    allergy_ids = fields.Many2many(
        'lcs.allergy', 'lcs_menu_item_allergy_rel', 'item_id', 'allergy_id',
        string='Contains Allergens',
    )

    school_id = fields.Many2one(
        'lcs.school', string='School',
        help='Optional. Restrict this item to a specific school.',
    )
