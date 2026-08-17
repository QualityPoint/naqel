// Copyright (c) 2026, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Pricing Rule", {
	setup(frm) {
		naqel.pricing.set_scope_type_query(frm, "items");
	},
});
