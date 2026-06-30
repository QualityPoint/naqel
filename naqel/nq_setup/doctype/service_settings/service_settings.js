// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Settings", {
	setup(frm) {
		naqel.pricing.set_scope_type_query(frm, "pricing_rule_priority");
		naqel.filters.credential_filter(frm, "credential_type", "credentials");
	},
});
