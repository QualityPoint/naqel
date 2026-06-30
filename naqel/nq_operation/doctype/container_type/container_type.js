// Copyright (c) 2025, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Container Type", {
	onload: function (frm) {
		// Setup all UOM filters using a helper function
		naqel.filters.uom_filter(frm, "Volume", "volume_unit");
		naqel.filters.uom_filter(frm, "Mass", "weight_unit");
	},
});
