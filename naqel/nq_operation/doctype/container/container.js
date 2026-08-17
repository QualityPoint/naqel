// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Container", {
	setup(frm) {
		frm.set_query("fill_level", function () {
			return {
				filters: { disabled: 0 },
			};
		});
	},

	refresh(frm) {
		if (!frm.is_new() && !frm.doc.qr_code) {
			frm.add_custom_button(__("Generate QR Code"), function () {
				frappe.call({
					method: "naqel.nq_operation.doctype.container.container.generate_qr_code",
					args: { name: frm.doc.name },
					callback() {
						frm.reload_doc();
					},
				});
			});
		}
	},
});
