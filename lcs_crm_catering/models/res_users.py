from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    default_email_cc = fields.Char(
        string='Default Cc Email',
        help='Comma-separated addresses that will pre-fill the Cc field of '
             'every email you compose (chatter or Send by Email wizard). '
             'Leave blank to disable.',
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['default_email_cc']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['default_email_cc']
