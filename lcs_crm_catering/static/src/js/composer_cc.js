/** @odoo-module **/
/*
 * Add "Cc:" support to the chatter composer.
 *
 * - Composer (data model): reactive `emailCc` string field, seeded to the
 *   current user's default from session_info.lcs_default_email_cc for every
 *   new composer instance (empty string if not configured).
 * - Composer (OWL component): `postData` includes `email_cc` so it reaches
 *   the /mail/message/post controller. lcs_crm_catering whitelists this
 *   key in mail.thread._get_allowed_message_params and forwards it to the
 *   generated mail.mail records inside message_post.
 * - Chatter template (chatter_cc.xml): renders a Cc input under the To: row,
 *   bound to state.thread.composer.emailCc.
 */
import { Composer as ComposerModel } from "@mail/core/common/composer_model";
import { Composer as ComposerComponent } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

// (1) Every composer instance starts with the user's default Cc if configured.
patch(ComposerModel.prototype, {
    setup() {
        super.setup?.();
        if (this.emailCc === undefined) {
            this.emailCc = session.lcs_default_email_cc || "";
        }
    },
});

// (2) Chain email_cc onto the payload sent to /mail/message/post.
patch(ComposerComponent.prototype, {
    get postData() {
        const data = super.postData;
        const cc = this.props.composer?.emailCc;
        if (cc && cc.trim()) {
            data.email_cc = cc.trim();
        }
        return data;
    },
});
