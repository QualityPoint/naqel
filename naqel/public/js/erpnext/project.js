frappe.ui.form.on("Project", {
    setup(frm) {
        frm.set_query("service_contract", function () {
            return {
                filters: {
                    company: frm.doc.company,
                    customer: frm.doc.customer,
                },
            };
        });
    },
});
