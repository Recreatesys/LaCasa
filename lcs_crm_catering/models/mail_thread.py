from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _get_allowed_message_params(self):
        # Whitelist email_cc so the /mail/message/post controller forwards it
        # to sudo().message_post() from the OWL chatter.
        return super()._get_allowed_message_params() | {'email_cc'}

    def message_post(self, **kwargs):
        email_cc = kwargs.pop('email_cc', None) or self.env.context.get('mail_post_email_cc')
        message = super().message_post(**kwargs)
        if email_cc and message:
            mails = self.env['mail.mail'].sudo().search([('mail_message_id', '=', message.id)])
            if mails:
                mails.write({'email_cc': email_cc})
        return message
