from odoo import fields, models


class LcsAllergy(models.Model):
    _name = 'lcs.allergy'
    _description = 'Food Allergy'
    _order = 'sequence, name'

    name = fields.Char(string='Allergy', required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Allergy name must be unique.'),
    ]
