from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        # Expose the current user's default Cc email to the frontend so the
        # OWL chatter composer can prefill state.thread.composer.emailCc
        # without an extra round-trip.
        result = super().session_info()
        if self.env.user._is_internal():
            result['lcs_default_email_cc'] = self.env.user.default_email_cc or ''
        return result
