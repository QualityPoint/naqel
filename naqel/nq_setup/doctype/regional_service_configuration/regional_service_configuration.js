// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Regional Service Configuration", {
    setup(frm) {
        frm.set_query("division", function () {
            return {
                filters: {
                    division_category: frm.doc.division_category
                }
            };
        });

        frm.set_query("service_configuration", function () {
            return {
                filters: {
                    service_type: frm.doc.service_type
                }
            };
        });
    },

    onload(frm) {
        // Set default volume unit from Naqel Settings for new documents in Reconfiguration mode
        if (frm.is_new() && !frm.doc.default_volume_unit && frm.doc.configuration_method === "Reconfiguration") {
            frappe.db.get_single_value("Naqel Settings", "default_volume_unit")
                .then(default_volume_unit => {
                    if (default_volume_unit) {
                        frm.set_value("default_volume_unit", default_volume_unit);
                    }
                });
        }
    },

    refresh(frm) {
        // Only apply calculations if in Reconfiguration mode
        if (frm.doc.configuration_method === "Reconfiguration") {
            if (frm.is_new()) {
                naqel.utils.calculate_threshold_statistics(frm);
                naqel.utils.calculate_volume_statistics(frm);
                naqel.utils.calculate_unit_generation_rate(frm);
            }
        }
    },

    configuration_method(frm) {
        // Clear reconfiguration fields when switching to Safety Factor
        if (frm.doc.configuration_method === "Safety Factor") {
            frm.set_value({
                "default_volume_unit": null,
                "calculate_generation_rate_by": null
            });
            frm.clear_table("generation_classification");
            frm.clear_table("ratings");
            frm.refresh_fields();
        } else if (frm.doc.configuration_method === "Reconfiguration") {
            // Set default volume unit
            if (!frm.doc.default_volume_unit) {
                frappe.db.get_single_value("Naqel Settings", "default_volume_unit")
                    .then(default_volume_unit => {
                        if (default_volume_unit) {
                            frm.set_value("default_volume_unit", default_volume_unit);
                        }
                    });
            }
        }
    },

    service_configuration(frm) {
        if (frm.doc.service_configuration) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    service_type: frm.doc.service_type,
                    doctype: "Service Configuration",
                    name: frm.doc.service_configuration
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value({
                            "isic_classification": r.message.isic_classification
                        });
                    }
                }
            });
        }
    },

    get_service_configuration(frm) {
        if (!frm.doc.service_type || !frm.doc.isic_classification) {
            frappe.msgprint(__("Please select both Service Type and ISIC Classification first"));
            return;
        }

        if (frm.doc.configuration_method !== "Reconfiguration") {
            frappe.msgprint(__("This button is only available in Reconfiguration mode"));
            return;
        }

        frappe.call({
            method: "naqel.nq_setup.doctype.regional_service_configuration.regional_service_configuration.get_service_configuration_data",
            args: {
                service_type: frm.doc.service_type,
                isic_classification: frm.doc.isic_classification
            },
            callback: function (r) {
                if (r.message) {
                    let data = r.message;

                    // Set main fields
                    frm.set_value({
                        "mean_threshold": data.mean_threshold,
                        "median_threshold": data.median_threshold,
                        "mean_volume": data.mean_volume,
                        "median_volume": data.median_volume,
                        "default_volume_unit": data.default_volume_unit,
                        "mean_generation_rate": data.mean_generation_rate,
                        "median_generation_rate": data.median_generation_rate,
                        "calculate_facility_wastes_by": data.calculate_facility_wastes_by,
                        "calculate_generation_rate_by": data.calculate_generation_rate_by
                    });

                    // Clear and populate generation classification
                    frm.clear_table("generation_classification");
                    if (data.generation_classification && data.generation_classification.length > 0) {
                        data.generation_classification.forEach(function (row) {
                            let child = frm.add_child("generation_classification");
                            child.max_threshold = row.max_threshold;
                            child.container_type = row.container_type;
                            child.container_standard_volume = row.container_standard_volume;
                            child.container_volume_unit = row.container_volume_unit;
                            child.count = row.count;
                            child.total_volume = row.total_volume;
                            child.conversion_factor = row.conversion_factor;
                            child.container_converted_volume = row.container_converted_volume;
                            child.total_converted_volume = row.total_converted_volume;
                        });
                    }

                    // Clear and populate ratings
                    frm.clear_table("ratings");
                    if (data.ratings && data.ratings.length > 0) {
                        data.ratings.forEach(function (row) {
                            let child = frm.add_child("ratings");
                            child.rating = row.rating;
                            child.safety_factor = row.safety_factor;
                        });
                    }

                    frm.refresh_fields();
                    frappe.show_alert({
                        message: __("Service Configuration data loaded successfully"),
                        indicator: "green"
                    });
                }
            }
        });
    },

    calculate_generation_rate_by(frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_unit_generation_rate(frm);
        }
    },

    mean_threshold(frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_unit_generation_rate(frm);
        }
    },

    median_threshold(frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_unit_generation_rate(frm);
        }
    },

    mean_volume(frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_unit_generation_rate(frm);
        }
    },

    median_volume(frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_unit_generation_rate(frm);
        }
    }
});

frappe.ui.form.on("Waste Generation Classification", {
    container_standard_volume: function (frm, cdt, cdn) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_row_volumes(frm, cdt, cdn, "volume_unit");
        }
    },

    count: function (frm, cdt, cdn) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_row_volumes(frm, cdt, cdn, "volume_unit");
        }
    },

    container_volume_unit: function (frm, cdt, cdn) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_row_volumes(frm, cdt, cdn, "volume_unit");
        }
    },

    max_threshold: function (frm, cdt, cdn) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_threshold_statistics(frm);
        }
    },

    total_converted_volume: function (frm, cdt, cdn) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_volume_statistics(frm);
        }
    },

    generation_classification_remove: function (frm) {
        if (frm.doc.configuration_method === "Reconfiguration") {
            naqel.utils.calculate_threshold_statistics(frm);
            naqel.utils.calculate_volume_statistics(frm);
        }
    }
});

// All calculation functions have been moved to naqel.utils (public/js/utilities/utils.js)

