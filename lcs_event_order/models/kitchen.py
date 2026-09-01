from odoo import fields, models


class Kitchen(models.Model):
    """A production kitchen an Event Order can be assigned to.

    C26a (client comment, slide 26) asks for a "Kitchen assigned" column on
    both worksheets. There was no kitchen or production-location list in the
    system at all, so this is it — deliberately empty on install. Add the real
    kitchens under Event Orders > Configuration > Kitchens; nothing is guessed
    on the client's behalf.
    """
    _name = 'lcs.kitchen'
    _description = 'Production Kitchen'
    _order = 'sequence, name'

    name = fields.Char(string='Kitchen', required=True)
    code = fields.Char(
        string='Short Code',
        help='Optional short form for worksheets and printouts, e.g. "TKW".',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'That kitchen already exists.'),
    ]
