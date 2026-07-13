from odoo import fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(
        string='Cc',
        help='Comma-separated CC email addresses. Every recipient of this '
             'message will also see the CC in their copy.',
    )

    def _prepare_mail_values_static(self):
        # Mass-mail path: creates mail.mail records directly.
        vals = super()._prepare_mail_values_static()
        if self.email_cc:
            vals['email_cc'] = self.email_cc
        return vals

    def _action_send_mail_comment(self, res_ids):
        # Comment path: routes through message_post — propagate via context.
        if self.email_cc:
            self = self.with_context(mail_post_email_cc=self.email_cc)
        return super()._action_send_mail_comment(res_ids)
