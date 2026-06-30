// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Operation Request", {
    setup(frm) {
        frm.set_query("container", function () {
            return {
                filters: {
                    "company": frm.doc.company,
                    "container_type": frm.doc.container_type
                }
            };
        });
    },
});
