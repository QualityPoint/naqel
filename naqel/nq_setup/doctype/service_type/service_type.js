// Copyright (c) 2025, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Type", {
	setup: function (frm) {
		// apply filter on item field 
		frm.set_query("item", function () {
			return {
				filters: {
					is_stock_item: 0,
					has_variants: 0,
					is_fixed_asset: 0,
				},
			};
		});

		frm.set_query("default_terms_and_conditions", function () {
			return {
				filters: {
					disabled: 0,
				},
			};
		});
	},

	onload: function (frm) {
		naqel.filters.uom_filter(frm, "Length", "diameter_uom");
	},

});
