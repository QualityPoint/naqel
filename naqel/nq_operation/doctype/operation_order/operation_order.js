// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Operation Order", {
    setup(frm) {
        frm.set_query("facility", function () {
            return {
                filters: [
                    ["link_doctype", "=", "Customer"],
                    ["link_name", "=", frm.doc.customer]
                ]
            };
        });

        frm.set_query("service_contract", function () {
            return {
                filters: {
                    customer: frm.doc.customer,
                    company: frm.doc.company
                }
            };
        });

        frm.set_query("project", function () {
            return {
                filters: {
                    customer: frm.doc.customer,
                    company: frm.doc.company
                }
            };
        });
    },
});
