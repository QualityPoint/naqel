// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

// Mount the per-row default waste item multi-select pills inside the
// waste_distributions child table (see utilities/waste_distribution_item.js).
naqel.bind_waste_item_editors("Waste Distribution", "waste_distributions");

frappe.ui.form.on("Service Configuration", {
    setup: function (frm) {
        frm.set_query("isic_classification", function () {
            return {
                filters: {
                    category_classification: frm.doc.isic_classification_category,
                },
            };
        });
    },

    onload(frm) {
        // Set default volume unit from Naqel Settings for new documents
        if (frm.is_new() && !frm.doc.default_volume_unit) {
            frappe.db.get_single_value("Naqel Settings", "default_volume_unit")
                .then(default_volume_unit => {
                    if (default_volume_unit) {
                        frm.set_value("default_volume_unit", default_volume_unit);
                    }
                });
        }
    },

    refresh(frm) {
        frm.set_df_property("waste_distributions", "cannot_delete_rows", 1);
        frm.set_df_property("waste_distributions", "cannot_add_rows", 1);

        if (frm.is_new()) {
            naqel.utils.calculate_threshold_statistics(frm);
            naqel.utils.calculate_volume_statistics(frm);
            naqel.utils.calculate_generation_rates(frm);
        }
    },

    service_type: function (frm) {
        if (!frm.doc.service_type) return;

        frappe.call({
            method: "naqel.nq_setup.doctype.service_configuration.service_configuration.get_waste_types",
            args: { service_type: frm.doc.service_type },
            callback: function (r) {
                frm.clear_table("waste_distributions");

                if (r.message?.waste_distributions?.length) {
                    r.message.waste_distributions.forEach(row => {
                        frm.add_child("waste_distributions", {
                            waste_type: row.waste_type,
                            is_group: row.is_group
                        });
                    });
                }

                frm.refresh_field("waste_distributions");
            }
        });
    },

    facility_uom: function (frm) {
        if (!frm.doc.facility_uom) return '';

        frappe.call({
            method: "naqel.nq_setup.doctype.service_configuration.service_configuration.get_facility_default_uom",
            args: { facility_uom: frm.doc.facility_uom },
            callback: function (r) {
                if (r.message) {
                    frm.set_value("default_facility_unit", r.message);
                }
            }
        });
    },

    mean_threshold: function (frm) {
        naqel.utils.calculate_generation_rates(frm);
    },

    median_threshold: function (frm) {
        naqel.utils.calculate_generation_rates(frm);
    },

    mean_volume: function (frm) {
        naqel.utils.calculate_generation_rates(frm);
    },

    median_volume: function (frm) {
        naqel.utils.calculate_generation_rates(frm);
    }
});

frappe.ui.form.on("Waste Generation Classification", {
    container_standard_volume: function (frm, cdt, cdn) {
        naqel.utils.calculate_row_volumes(frm, cdt, cdn);
    },

    count: function (frm, cdt, cdn) {
        naqel.utils.calculate_row_volumes(frm, cdt, cdn);
    },

    container_volume_unit: function (frm, cdt, cdn) {
        naqel.utils.calculate_row_volumes(frm, cdt, cdn);
    },

    max_threshold: function (frm, cdt, cdn) {
        naqel.utils.calculate_threshold_statistics(frm);
    },

    total_converted_volume: function (frm, cdt, cdn) {
        naqel.utils.calculate_volume_statistics(frm);
    },

    generation_classification_remove: function (frm) {
        naqel.utils.calculate_threshold_statistics(frm);
        naqel.utils.calculate_volume_statistics(frm);
    }
});

// All calculation functions have been moved to naqel.utils (public/js/utilities/utils.js)
