// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address Division", {
	refresh(frm) {
		apply_parent_constraints(frm);
	},

	country(frm) {
		frm.set_value("parent_division", "");
	},

	division_category(frm) {
		frm.set_value("parent_division", "");
		apply_parent_constraints(frm);
	},
});

function apply_parent_constraints(frm) {
	// Province (root) has no parent; every other level requires a parent of the
	// category directly above it. The hierarchy lives on the server, so we ask it
	// for the expected parent category rather than duplicating it here.
	const category = frm.doc.division_category;
	if (!category) return;

	frappe.call({
		method: "naqel.nq_setup.doctype.address_division.address_division.get_parent_division_category",
		args: { division_category: category },
		callback(r) {
			const parent_category = r.message; // null for the root (Province)

			frm.set_df_property("parent_division", "reqd", parent_category ? 1 : 0);
			frm.set_df_property("parent_division", "read_only", parent_category ? 0 : 1);

			frm.set_query("parent_division", function () {
				const filters = { is_group: 1, country: frm.doc.country };
				if (parent_category) filters.division_category = parent_category;
				return { filters };
			});
		},
	});
}
