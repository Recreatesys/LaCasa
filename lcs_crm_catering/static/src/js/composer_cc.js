/** @odoo-module **/
/*
 * Add "Cc:" support to the chatter composer.
 *
 * - Composer (data model): reactive `emailCc` string field, seeded to "" for
 *   every new composer instance.
 * - Composer (OWL component): `postData` includes `email_cc` so it reaches the
 *   /mail/message/post controller. lcs_crm_catering also whitelists this key
 *   in mail.thread._get_allowed_message_params and forwards it to the
 *   generated mail.mail records inside message_post.
 * - Chatter template: renders a Cc input right under the To: row, bound to
 *   state.thread.composer.emailCc.
 */
import { Composer as ComposerModel } from "@mail/core/common/composer_model";
import { Composer as ComposerComponent } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";

// (1) Ensure every composer instance has an `emailCc` string property. We
// initialise it lazily in a getter/setter pair so OWL's reactive Proxy picks
// up subsequent writes and re-renders the input.
patch(ComposerModel.prototype, {
    setup() {
        super.setup?.();
        if (this.emailCc === undefined) {
            this.emailCc = "";
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
