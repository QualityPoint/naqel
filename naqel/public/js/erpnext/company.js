frappe.ui.form.on("Company", {
    setup(frm) {
        naqel.filters.credential_filter(frm, "credential_type", "credentials");
    },
});

frappe.ui.form.on("Company Credential", {
    credential: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.credential || !row.credential_type || !row.document_type) return;

        frappe.call({
            method: "naqel.utils.document_parser.api.parse_credential_document",
            args: {
                file_url: row.credential,
                credential_type: row.credential_type,
                document_type: row.document_type,
            },
            freeze: true,
            freeze_message: __("Parsing document…"),
            callback: function (r) {
                if (!r.message) return;
                const result = r.message;

                if (result.document_number) {
                    frappe.model.set_value(cdt, cdn, "document_number", result.document_number);
                }
                if (result.display_html) {
                    frappe.model.set_value(cdt, cdn, "document_display", result.display_html);
                }

                if (!result.success) {
                    frappe.msgprint({
                        title: __("Document Parsing"),
                        message: result.error || __("Could not extract document number."),
                        indicator: "orange",
                    });
                } else if (result.warnings && result.warnings.length) {
                    frappe.msgprint({
                        title: __("Document Parsing — Warnings"),
                        message: result.warnings.join("<br>"),
                        indicator: "yellow",
                    });
                }
            },
        });
    },
});