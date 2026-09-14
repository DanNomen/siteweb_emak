/** @odoo-module **/

import { AttachmentView } from "@mail/core/common/attachment_view";

if (AttachmentView) {
    AttachmentView.props = {
        ...AttachmentView.props,
        threadId: { optional: true },
        threadModel: { optional: true },
        "*": true,
    };
}
