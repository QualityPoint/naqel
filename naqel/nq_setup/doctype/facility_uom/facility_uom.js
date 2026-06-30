// Copyright (c) 2025, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facility UOM", {
	setup(frm) {
		frm.set_query("default_uom", function () {
			return {
				filters: {
					enabled: 1,
					must_be_whole_number: frm.doc.must_be_whole_number,
				},
			};
		});

		frm.set_query("subsidiary_uom", function () {
			return {
				filters: {
					name: ["!=", frm.doc.name],
				},
			};
		});
	},
});
