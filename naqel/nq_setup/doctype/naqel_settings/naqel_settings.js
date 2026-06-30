// Copyright (c) 2025, QuailtyPoint and contributors
// For license information, please see license.txt


frappe.ui.form.on("Naqel Settings", {
	onload: function (frm) {
		// Setup all UOM filters using a helper function
		naqel.filters.uom_filter(frm, "Volume", "default_volume_unit");
		naqel.filters.uom_filter(frm, "Mass", "default_mass_unit");
		naqel.filters.uom_filter(frm, "Length", "default_length_unit");
		naqel.filters.uom_filter(frm, "Density", "default_density_unit");
		naqel.filters.uom_filter(frm, "Area", "default_area_unit");
	},

	generate_demo_data: function (frm) {
		frappe.confirm(
			__("Are you sure you want to generate demo data?<br>This will create sample records for Facility UOM, Container Type, Waste Removal Mechanism, and Service Configuration."),
			function () {
				frappe.call({
					method: "naqel.custom.demo_data.generate_all_demo_data",
					freeze: true,
					freeze_message: __("Generating demo data..."),
					callback: function (r) {
						frm.reload_doc();
					}
				});
			}
		);
	},

	clear_demo_data: function (frm) {
		// Show dialog to select doctypes to clear
		let dialog = new frappe.ui.Dialog({
			title: __("Clear Demo Data"),
			fields: [
				{
					fieldname: "doctypes",
					fieldtype: "MultiCheck",
					label: __("Select DocTypes to Clear"),
					options: [
						{ label: __("Facility UOM"), value: "Facility UOM" },
						{ label: __("Container Type"), value: "Container Type" },
						{ label: __("Waste Removal Mechanism"), value: "Waste Removal Mechanism" },
						{ label: __("Service Configuration"), value: "Service Configuration" }
					],
					reqd: 1
				}
			],
			primary_action_label: __("Clear Selected"),
			primary_action: function (values) {
				if (!values.doctypes || values.doctypes.length === 0) {
					frappe.msgprint(__("Please select at least one doctype"));
					return;
				}

				frappe.confirm(
					__("Are you sure you want to delete all records from the selected doctypes?<br>This action cannot be undone."),
					function () {
						frappe.call({
							method: "naqel.custom.demo_data.clear_demo_data",
							args: {
								doctypes: values.doctypes
							},
							freeze: true,
							freeze_message: __("Clearing demo data..."),
							callback: function (r) {
								dialog.hide();
								frm.reload_doc();
							}
						});
					}
				);
			}
		});

		dialog.show();
	}
});
