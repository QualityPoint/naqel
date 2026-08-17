// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Waste Type", {
	onload: function (frm) {
		frm.list_route = "Tree/Waste Type";
		naqel.filters.uom_filter(frm, "Density", "waste_density_unit");

		frm.fields_dict["parent_waste_type"].get_query = function (doc, cdt, cdn) {
			return {
				filters: [
					["Waste Type", "is_group", "=", 1],
					["Waste Type", "name", "!=", doc.name],
				],
			};
		};
	},

	refresh: function (frm) {
		frm.trigger("set_root_readonly");
		frm.add_custom_button(__("Waste Type Tree"), function () {
			frappe.set_route("Tree", "Waste Type");
		});

		// Add Calculate Average Density button for parent waste types
		if (frm.doc.is_group && !frm.doc.__islocal) {
			frm.add_custom_button(__("Calculate Average Density"), function () {
				frappe.call({
					method: "calculate_average_density",
					doc: frm.doc,
					callback: function (r) {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
				});
			});
		}
	},

	set_root_readonly: function (frm) {
		// read-only for root waste type group
		frm.set_intro("");
		if (!frm.doc.parent_waste_type && !frm.doc.__islocal) {
			frm.set_read_only();
			frm.set_intro(__("This is a root waste type group and cannot be edited."), true);
		}
	},

	page_name: frappe.utils.warn_page_name_change,
});
