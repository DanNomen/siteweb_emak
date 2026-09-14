/** @odoo-module **/

import { AttachmentView } from "@mail/core/common/attachment_view";

if (AttachmentView) {
    AttachmentView.props = {
        threadId: { type: "*", optional: true },
        threadModel: { type: "*", optional: true },
    };
}
