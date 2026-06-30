// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Pricing Rule", {
	setup(frm) {
		naqel.pricing.set_scope_type_query(frm, "items");
	},
});
