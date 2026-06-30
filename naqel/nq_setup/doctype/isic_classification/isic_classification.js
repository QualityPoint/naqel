// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("ISIC Classification", {
    setup(frm) {
        frm.set_query("parent_category", function () {
            return {
                query: "naqel.nq_setup.doctype.isic_classification.isic_classification.get_parent_categories",
                filters: {
                    category_classification: frm.doc.category_classification,
                },
            };
        });
    },
});
