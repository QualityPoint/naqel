// Copyright (c) 2026, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
	refresh(frm) {
		// Add "Facility" to the existing Lead "Create" button group (alongside
		// Customer / Opportunity / Quotation / Prospect). Only for saved leads,
		// since the new Facility is linked back to this Lead by name.
		if (frm.is_new()) return;

		frm.add_custom_button(
			__("Facility"),
			() => create_facility_from_lead(frm),
			__("Create")
		);
	},
});

function create_facility_from_lead(frm) {
	// Open a new Facility pre-linked to this Lead via its Dynamic Link table.
	frappe.model.with_doctype("Facility", function () {
		const facility = frappe.model.get_new_doc("Facility");
		const link = frappe.model.add_child(facility, "Dynamic Link", "links");
		link.link_doctype = "Lead";
		link.link_name = frm.doc.name;
		link.link_title = frm.doc.lead_name || frm.doc.name;
		frappe.set_route("Form", "Facility", facility.name);
	});
}
