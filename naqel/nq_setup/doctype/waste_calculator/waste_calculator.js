// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

// Mount the per-row waste item multi-select pills inside the `wastes` child table,
// reusing the same editor as Service Configuration (see utilities/waste_distribution_item.js).
naqel.bind_waste_item_editors("WC Facility Waste Item", "wastes", {
    storage_field: "waste_item",
    html_field: "waste_item_html",
    label: __("Waste Item"),
});

frappe.ui.form.on("Waste Calculator", {
    setup(frm) {
        naqel.filters.isic_filter(frm, "isic_classification");
    },

    refresh(frm) {
        frm.disable_save();
        setup_service_configuration_query(frm);

        // Rows mirror the applied configuration: lock structure but keep the
        // waste_item pills editable.
        frm.set_df_property("wastes", "cannot_add_rows", 1);
        frm.set_df_property("wastes", "cannot_delete_rows", 1);

        // Add Calculate button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Calculate'), function () {
                calculate_waste_generation(frm);
            }).addClass('btn-primary');

            frm.add_custom_button(__('Clear Form'), function () {
                clear_calculator_form(frm);
            });
        }
    },

    service_type: function (frm) {
        if (frm.doc.service_type) {
            // Populate wastes from the applied configuration if ISIC is also selected
            fetch_and_populate_wastes(frm);
            setup_service_configuration_query(frm);
        }
    },

    isic_classification: function (frm) {
        if (frm.doc.isic_classification) {
            // Populate wastes from the applied configuration after setting isic
            fetch_and_populate_wastes(frm);
            setup_service_configuration_query(frm);
        }
    },

    service_configuration: function (frm) {
        if (frm.doc.service_configuration) {
            setup_facility_uom_filter(frm);
        }
    },

    facility_uom: function (frm) {
        if (frm.doc.facility_uom) {
            frappe.call({
                method: 'naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_facility_uom_details',
                args: {
                    facility_uom: frm.doc.facility_uom
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value({
                            'must_be_whole_number': r.message.must_be_whole_number,
                            'is_composite_uom': r.message.is_composite_uom
                        });
                    }
                }
            });

            populate_facility_measurements(frm);
        }
    },

    calculation_based_on: function (frm) {
        // Switching SC/RSC invalidates the chosen config; re-scope the picker.
        frm.set_value('service_configuration', '');
        setup_service_configuration_query(frm);
        clear_calculation_results(frm);
    },

    territory: function (frm) {
        // Territory narrows the Regional Service Configuration picker.
        if (frm.doc.calculation_based_on === 'Regional Service Configuration') {
            frm.set_value('service_configuration', '');
            setup_service_configuration_query(frm);
        }
    },

    facility_rating: function (frm) {
        // Snap to a whole star unless fractional ratings are enabled in Service Settings.
        naqel.enforce_whole_rating(frm, null, null, 'facility_rating');
    }
});

/**
 * Main calculation function
 * @param {Object} frm - Frappe form object
 */
function calculate_waste_generation(frm) {
    // Validate required fields
    if (!frm.doc.service_type) {
        frappe.msgprint(__('Please select a Service Type'));
        return;
    }

    if (!frm.doc.isic_classification) {
        frappe.msgprint(__('Please select an ISIC Classification'));
        return;
    }

    if (!frm.doc.facility_uom) {
        frappe.msgprint(__('Please select a Facility UOM'));
        return;
    }

    if (!frm.doc.calculation_based_on) {
        frappe.msgprint(__('Please select Calculation Based On'));
        return;
    }

    // Validate measurements
    if (frm.doc.is_composite_uom) {
        if (!frm.doc.facility_measurements || frm.doc.facility_measurements.length === 0) {
            frappe.msgprint(__('Please provide Facility Measurements'));
            return;
        }
    } else {
        if (!frm.doc.facility_measurement || frm.doc.facility_measurement <= 0) {
            frappe.msgprint(__('Please provide a valid Facility Measurement'));
            return;
        }
    }

    // Waste Item is mandatory per row (the table is virtual / not saved, so the
    // child field's reqd flag isn't enforced automatically).
    const missing_item = (frm.doc.wastes || []).find(row => !(row.waste_item || '').trim());
    if (missing_item) {
        frappe.msgprint(__('Please select at least one Waste Item for every waste row'));
        return;
    }

    frappe.call({
        method: 'naqel.nq_setup.doctype.waste_calculator.waste_calculator.calculate_waste',
        args: {
            doc: frm.doc
        },
        callback: function (r) {
            if (r.message) {
                // Update calculation results
                frm.set_value({
                    'facility_unit_generation_rate': r.message.facility_unit_generation_rate,
                    'regional_safety_factor': r.message.regional_safety_factor,
                    'rating_safety_factor': r.message.rating_safety_factor,
                    'facility_generated_waste': r.message.facility_generated_waste,
                    'total_generated_waste': r.message.total_generated_waste,
                    'suggested_container': r.message.suggested_container,
                    'suggested_container_count': r.message.suggested_container_count,
                    'waste_calculation': r.message.waste_calculation,
                    'configuration_remarks': r.message.configuration_remarks
                });

                // Populate generated_wastes (one row per suggested container).
                frm.clear_table('generated_wastes');
                (r.message.generated_wastes || []).forEach(function (row) {
                    frm.add_child('generated_wastes', row);
                });
                frm.refresh_field('generated_wastes');

                frappe.show_alert({
                    message: __('Waste calculation completed successfully'),
                    indicator: 'green'
                }, 5);
            }
        }
    });
}

/**
 * Clear calculator form
 * @param {Object} frm - Frappe form object
 */
function clear_calculator_form(frm) {
    frappe.confirm(
        __('Are you sure you want to clear all fields?'),
        function () {
            // Clear all fields
            frm.clear_table('wastes');
            frm.clear_table('facility_measurements');
            frm.clear_table('generated_wastes');

            frm.set_value({
                'service_type': '',
                'isic_classification': '',
                'service_configuration': '',
                'calculation_based_on': '',
                'configuration_remarks': '',
                'facility_uom': '',
                'is_composite_uom': 0,
                'facility_measurement': 0,
                'facility_rating': 0,
                'facility_unit_generation_rate': 0,
                'regional_safety_factor': 0,
                'rating_safety_factor': 0,
                'facility_generated_waste': 0,
                'total_generated_waste': 0,
                'suggested_container': '',
                'suggested_container_count': 0,
                'waste_calculation': ''
            });

            frm.refresh();
        }
    );
}

/**
 * Clear only calculation results
 * @param {Object} frm - Frappe form object
 */
function clear_calculation_results(frm) {
    frm.set_value({
        'facility_unit_generation_rate': 0,
        'regional_safety_factor': 0,
        'rating_safety_factor': 0,
        'facility_generated_waste': 0,
        'total_generated_waste': 0,
        'suggested_container': '',
        'suggested_container_count': 0,
        'waste_calculation': '',
        'configuration_remarks': ''
    });
    frm.clear_table('generated_wastes');
    frm.refresh_field('generated_wastes');
}

/**
 * Fetch the applied Service Configuration's waste distributions and populate the
 * `wastes` table. Each row mirrors a configuration distribution: waste_type and
 * percentage are read-only, while waste_item is pre-filled from the config's
 * default_waste_item and remains editable via the pills control.
 * @param {Object} frm - Frappe form object
 */
function fetch_and_populate_wastes(frm) {
    // Validate required fields
    if (!frm.doc.isic_classification || !frm.doc.service_type) {
        return;
    }

    frappe.call({
        method: 'naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_service_configuration',
        args: {
            isic_classification: frm.doc.isic_classification,
            service_type: frm.doc.service_type
        },
        callback: function (r) {
            if (r.message) {
                // Pre-fill the default Service Configuration only in SC mode; in
                // Regional mode the user picks an RSC explicitly.
                if (r.message.service_configuration && frm.doc.calculation_based_on !== 'Regional Service Configuration') {
                    frm.set_value('service_configuration', r.message.service_configuration);
                }

                // Populate wastes from the configuration's distributions.
                frm.clear_table('wastes');

                if (r.message.waste_distributions && r.message.waste_distributions.length > 0) {
                    r.message.waste_distributions.forEach(function (row) {
                        frm.add_child('wastes', {
                            waste_type: row.waste_type,
                            percentage: row.distribution_percentage,
                            waste_item: row.default_waste_item || ''
                        });
                    });
                }

                frm.refresh_field('wastes');
            }
        }
    });
}

/**
 * Setup query filter for facility_uom based on Service Configuration
 * Auto-populates the default facility_uom from the configuration
 * @param {Object} frm - Frappe form object
 */
/**
 * Scope the service_configuration picker (Dynamic Link) to Service Configurations or
 * Regional Service Configurations matching the service type / ISIC walk (+ territory
 * for regional). Reuses the Service Quotation query functions.
 */
function setup_service_configuration_query(frm) {
    if (!frm.doc.service_type) return;

    if (frm.doc.calculation_based_on === 'Regional Service Configuration') {
        frm.set_query('service_configuration', function () {
            return {
                query: 'naqel.nq_crm.doctype.service_quotation.service_quotation.query_regional_service_configurations',
                filters: {
                    service_type: frm.doc.service_type,
                    isic_classification: frm.doc.isic_classification || '',
                    territory: frm.doc.territory || ''
                }
            };
        });
    } else {
        frm.set_query('service_configuration', function () {
            return {
                query: 'naqel.nq_crm.doctype.service_quotation.service_quotation.query_service_configurations',
                filters: {
                    service_type: frm.doc.service_type,
                    isic_classification: frm.doc.isic_classification || ''
                }
            };
        });
    }
}

function setup_facility_uom_filter(frm) {
    if (!frm.doc.service_configuration) {
        return;
    }

    clear_facility_measurements(frm);

    // The server resolves the chosen configuration (a Regional Service Configuration
    // to the config it computes from) and returns the allowed Facility UOMs with the
    // default first.
    frappe.call({
        method: 'naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_allowed_facility_uoms',
        args: {
            service_configuration: frm.doc.service_configuration
        },
        callback: function (r) {
            const allowed = r.message || [];
            if (!allowed.length) return;

            frm.set_query('facility_uom', function () {
                return {
                    filters: [
                        ['Facility UOM', 'name', 'in', allowed]
                    ]
                };
            });

            // Auto-populate the configuration's default Facility UOM (first entry);
            // this drives the measurement hierarchy via the facility_uom handler.
            frm.set_value('facility_uom', allowed[0]);
        }
    });
}

/**
 * Populate facility_measurements child table with UOM hierarchy
 * @param {Object} frm - Frappe form object
 */
function populate_facility_measurements(frm) {
    if (!frm.doc.facility_uom) {
        return;
    }

    frappe.call({
        method: 'naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_facility_uom_hierarchy',
        args: {
            facility_uom: frm.doc.facility_uom
        },
        callback: function (r) {
            if (r.message && r.message.length > 0) {
                // Populate with UOM hierarchy
                r.message.forEach(function (uom_data) {
                    frm.add_child('facility_measurements', {
                        uom: uom_data.uom,
                        must_be_whole_number: uom_data.must_be_whole_number || 0,
                        is_composite_uom: uom_data.is_composite_uom || 0,
                        uom_value: 0
                    });
                });

                // Refresh field to show updated table
                frm.refresh_field('facility_measurements');
            }
        }
    });
}

function clear_facility_measurements(frm) {
    // Clear pre-entered facility UOM data
    frm.set_value({
        'facility_uom': '',
        'is_composite_uom': 0,
        'must_be_whole_number': 0,
        'facility_measurement': 0
    });

    frm.clear_table('facility_measurements');
    frm.refresh_field('facility_measurements');
}

frappe.ui.form.on("Calc Facility Measurements", {
    uom_value: function (frm, cdt, cdn) {
        // Calculate total facility measurement from child table
        let total_measurement = 1;
        frm.doc.facility_measurements.forEach(function (row) {
            total_measurement *= row.uom_value || 1;
        });

        frm.set_value('facility_measurement', total_measurement);
    }
});