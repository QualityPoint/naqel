frappe.provide("naqel.utils");

naqel.utils = {
    /**
     * Resolve the default Address linked to any document (Company, Customer,
     * Facility, etc.) via the Dynamic Link table. Generic helper shared by
     * Service Quotation, Service Contract, and Operation Order.
     * Returns a Promise resolving to the Address name (or null when none).
     * @param {string} link_doctype - The linked doctype, e.g. "Facility"
     * @param {string} link_name - The document name to resolve the address for
     * @returns {Promise<string|null>}
     */
    get_default_address(link_doctype, link_name) {
        if (!link_name) {
            return Promise.resolve(null);
        }

        return frappe.call({
            method: "naqel.utils.utils.get_default_address",
            args: { link_doctype, link_name }
        }).then(r => r.message || null);
    },

    /**
     * Calculate duration between two dates (inclusive of both ends) via the server.
     * Generic helper shared by Service Quotation, Service Contract, and Operation Order.
     * Returns a Promise resolving to the numeric duration (0 when any input is missing).
     * @param {string} start_date
     * @param {string} end_date
     * @param {string} duration_uom - "Day", "Month", or "Year"
     * @returns {Promise<number>}
     */
    calculate_duration(start_date, end_date, duration_uom) {
        if (!(start_date && end_date && duration_uom)) {
            return Promise.resolve(0);
        }

        return frappe.call({
            method: "naqel.utils.duration.calculate_duration",
            args: { start_date, end_date, duration_uom }
        }).then(r => r.message ?? 0);
    },

    /**
     * Calculate threshold statistics (mean and median) from generation classification
     * @param {object} frm - The form object
     */
    calculate_threshold_statistics(frm) {
        // Extract valid max_threshold values
        const thresholds = frm.doc.generation_classification
            ?.filter(row => row.max_threshold && row.max_threshold > 0)
            .map(row => row.max_threshold) || [];

        if (thresholds.length > 0) {
            const mean_threshold = thresholds.reduce((sum, val) => sum + val, 0) / thresholds.length;
            const sorted = [...thresholds].sort((a, b) => a - b);
            const mid = Math.floor(sorted.length / 2);
            const median_threshold = sorted.length % 2 === 0
                ? (sorted[mid - 1] + sorted[mid]) / 2
                : sorted[mid];

            frm.set_value("mean_threshold", mean_threshold);
            frm.set_value("median_threshold", median_threshold);
        } else {
            frm.set_value("mean_threshold", 0);
            frm.set_value("median_threshold", 0);
        }
    },

    /**
     * Calculate volume statistics (mean and median) from generation classification
     * @param {object} frm - The form object
     */
    calculate_volume_statistics(frm) {
        // Extract valid total_converted_volume values
        const volumes = frm.doc.generation_classification
            ?.filter(row => row.total_converted_volume && row.total_converted_volume > 0)
            .map(row => row.total_converted_volume) || [];

        if (volumes.length > 0) {
            const mean_volume = volumes.reduce((sum, val) => sum + val, 0) / volumes.length;
            const sorted = [...volumes].sort((a, b) => a - b);
            const mid = Math.floor(sorted.length / 2);
            const median_volume = sorted.length % 2 === 0
                ? (sorted[mid - 1] + sorted[mid]) / 2
                : sorted[mid];

            frm.set_value("mean_volume", mean_volume);
            frm.set_value("median_volume", median_volume);
        } else {
            frm.set_value("mean_volume", 0);
            frm.set_value("median_volume", 0);
        }
    },

    /**
     * Calculate generation rates (Service Configuration version)
     * @param {object} frm - The form object
     */
    calculate_generation_rates(frm) {
        // Calculate mean generation rate: mean_volume / mean_threshold
        if (frm.doc.mean_threshold && frm.doc.mean_threshold > 0) {
            frm.set_value("mean_generation_rate", frm.doc.mean_volume / frm.doc.mean_threshold);
        } else {
            frm.set_value("mean_generation_rate", 0);
        }

        // Calculate median generation rate: median_volume / median_threshold
        if (frm.doc.median_threshold && frm.doc.median_threshold > 0) {
            frm.set_value("median_generation_rate", frm.doc.median_volume / frm.doc.median_threshold);
        } else {
            frm.set_value("median_generation_rate", 0);
        }
    },

    /**
     * Calculate unit generation rate (Regional Service Configuration version)
     * @param {object} frm - The form object
     */
    calculate_unit_generation_rate(frm) {
        // Calculate generation rates based on calculate_generation_rate_by selection
        if (frm.doc.calculate_generation_rate_by === "Mean") {
            if (frm.doc.mean_threshold && frm.doc.mean_threshold > 0) {
                frm.set_value("mean_generation_rate", frm.doc.mean_volume / frm.doc.mean_threshold);
            } else {
                frm.set_value("mean_generation_rate", 0);
            }
            // Clear median rate when using Mean
            frm.set_value("median_generation_rate", 0);
        } else if (frm.doc.calculate_generation_rate_by === "Median") {
            if (frm.doc.median_threshold && frm.doc.median_threshold > 0) {
                frm.set_value("median_generation_rate", frm.doc.median_volume / frm.doc.median_threshold);
            } else {
                frm.set_value("median_generation_rate", 0);
            }
            // Clear mean rate when using Median
            frm.set_value("mean_generation_rate", 0);
        }
    },

    /**
     * Calculate total volume for a row (container_standard_volume * count)
     * @param {object} row - The child table row
     */
    calculate_total_volume(row) {
        if (row.container_standard_volume && row.count) {
            row.total_volume = row.container_standard_volume * row.count;
        } else {
            row.total_volume = 0;
        }
    },

    /**
     * Calculate converted volumes for a row
     * @param {object} frm - The form object
     * @param {object} row - The child table row
     * @param {string} volume_unit_field - The field name for volume unit (default_volume_unit or volume_unit)
     */
    calculate_converted_volumes(frm, row, volume_unit_field = "default_volume_unit") {
        const volume_unit = frm.doc[volume_unit_field];

        if (!volume_unit) {
            row.conversion_factor = 0;
            row.container_converted_volume = 0;
            row.total_converted_volume = 0;
            return;
        }

        // If same unit, conversion factor is 1
        if (row.container_volume_unit === volume_unit) {
            row.conversion_factor = 1;
            row.container_converted_volume = row.container_standard_volume || 0;
            row.total_converted_volume = row.total_volume || 0;
            return;
        }

        if (!row.container_volume_unit) {
            row.conversion_factor = 0;
            row.container_converted_volume = 0;
            row.total_converted_volume = 0;
            return;
        }

        // Get conversion factor from server
        frappe.call({
            method: "naqel.nq_setup.doctype.service_configuration.service_configuration.get_uom_conversion_factor",
            args: {
                from_uom: row.container_volume_unit,
                to_uom: volume_unit
            },
            async: false,
            callback: function (r) {
                if (r.message) {
                    row.conversion_factor = r.message;
                    row.container_converted_volume = (row.container_standard_volume || 0) * r.message;
                    row.total_converted_volume = (row.total_volume || 0) * r.message;
                } else {
                    row.conversion_factor = 1;
                    row.container_converted_volume = row.container_standard_volume || 0;
                    row.total_converted_volume = row.total_volume || 0;
                }
            }
        });
    },

    /**
     * Resolve the Service / Regional Configuration for the form's current
     * facility + service_type + territory. Shared by Service Request and
     * Service Quotation.
     */
    resolve_facility_configuration(frm) {
        if (!frm.doc.service_type || !frm.doc.facility) return;

        frappe.call({
            method: "naqel.nq_crm.doctype.service_quotation.service_quotation.get_resolved_configuration",
            args: {
                service_type: frm.doc.service_type,
                facility: frm.doc.facility,
                territory: frm.doc.territory,
            },
            callback: function (r) {
                if (!r.message) return;
                frappe.run_serially([
                    () => frm.set_value("calculation_based_on", r.message.calculation_based_on || ""),
                    () => frm.set_value("service_configuration", r.message.service_configuration || ""),
                ]);
            },
        });
    },

    /**
     * Fetch the UOM conversion factor for the selected facility_uom relative
     * to the Service Configuration's default UOM.
     */
    fetch_conversion_factor(frm) {
        if (!frm.doc.service_configuration || !frm.doc.facility_uom) {
            frm.set_value("conversion_factor", 1);
            naqel.utils.recompute_net_facility_measurement(frm);
            return;
        }

        frappe.call({
            method: "naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_uom_conversion_factor",
            args: {
                service_configuration: frm.doc.service_configuration,
                facility_uom: frm.doc.facility_uom,
            },
            callback: function (r) {
                frm.set_value("conversion_factor", r.message || 1);
                naqel.utils.recompute_net_facility_measurement(frm);
            },
        });
    },

    /**
     * Recalculate net_facility_measurement = facility_measurement × conversion_factor.
     */
    recompute_net_facility_measurement(frm) {
        const measurement = flt(frm.doc.facility_measurement);
        const factor = flt(frm.doc.conversion_factor || 1);
        frm.set_value("net_facility_measurement", measurement * factor);
    },

    /**
     * Populate the facility_uoms child table from the UOM hierarchy
     * (composite vs simple). After populating, recomputes the measurement.
     */
    populate_facility_uoms(frm) {
        if (!frm.doc.facility_uom) return;

        frappe.call({
            method: "naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_facility_uom_hierarchy",
            args: { facility_uom: frm.doc.facility_uom },
            callback: function (r) {
                const hierarchy = r.message || [];
                frm.clear_table("facility_uoms");

                const is_composite = hierarchy.length && hierarchy[0].is_composite_uom;
                if (is_composite) {
                    hierarchy.forEach(function (uom_data) {
                        frm.add_child("facility_uoms", {
                            uom: uom_data.uom,
                            must_be_whole_number: uom_data.must_be_whole_number,
                            is_composite_uom: uom_data.is_composite_uom,
                            uom_value: 0,
                        });
                    });
                } else {
                    frm.set_value("facility_measurement", 0);
                }
                frm.refresh_field("facility_uoms");
                naqel.utils.recompute_facility_measurement(frm);
            },
        });
    },

    /**
     * Recompute facility_measurement as the product of all uom_value rows
     * (composite mode). Cascades into net_facility_measurement.
     */
    recompute_facility_measurement(frm) {
        const rows = frm.doc.facility_uoms || [];
        if (!rows.length) return;

        const total = rows.reduce((product, row) => product * (row.uom_value || 0), 1);
        frm.set_value("facility_measurement", total);
        naqel.utils.recompute_net_facility_measurement(frm);
    },

    /**
     * Restrict facility_uom to the UOMs allowed by the applied configuration.
     */
    setup_facility_uom_filter(frm) {
        if (!frm.doc.service_configuration) return;

        const base_sc_promise =
            frm.doc.calculation_based_on === "Regional Service Configuration"
                ? frappe.db
                        .get_value("Regional Service Configuration", frm.doc.service_configuration, "service_configuration")
                        .then(r => (r.message ? r.message.service_configuration : null))
                : Promise.resolve(frm.doc.service_configuration);

        base_sc_promise.then(base_sc => {
            if (!base_sc) return;
            frappe.call({
                method: "naqel.nq_setup.doctype.waste_calculator.waste_calculator.get_allowed_facility_uoms",
                args: { service_configuration: base_sc },
                callback: function (r) {
                    if (r.message && r.message.length) {
                        frm.set_query("facility_uom", () => ({
                            filters: [["Facility UOM", "name", "in", r.message]],
                        }));
                        frm.refresh_field("facility_uom");
                    }
                },
            });
        });
    },

    /**
     * Calculate row volumes (combines total and converted volume calculations)
     * @param {object} frm - The form object
     * @param {string} cdt - Child doctype name
     * @param {string} cdn - Child docname
     * @param {string} volume_unit_field - The field name for volume unit (default_volume_unit or volume_unit)
     */
    calculate_row_volumes(frm, cdt, cdn, volume_unit_field = "default_volume_unit") {
        let row = locals[cdt][cdn];

        // Calculate total_volume = container_standard_volume * count
        this.calculate_total_volume(row);

        // Calculate converted volumes
        this.calculate_converted_volumes(frm, row, volume_unit_field);

        frm.refresh_field("generation_classification");

        // Update statistics after row calculation
        this.calculate_volume_statistics(frm);
    }
};
