// Copyright (c) 2025, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Request", {
    setup(frm) {
        frm.set_query("request_from", function () {
            return {
                filters: {
                    name: ["in", ["Customer", "Lead"]],
                },
            };
        });

        frm.set_query("facility", function () {
            if (!frm.doc.request_from || !frm.doc.party) return;
            return {
                filters: [
                    ["link_doctype", "=", frm.doc.request_from],
                    ["link_name", "=", frm.doc.party],
                ],
            };
        });
    },

    request_from(frm) {
        frm.set_value("party", "");
        frm.set_value("customer_name", "");
        frm.set_value("facility", "");
    },

    party(frm) {
        frm.set_value("facility", "");
        if (frm.doc.party && frm.doc.request_from) {
            frappe.call({
                method: "naqel.utils.utils.get_party_details",
                args: {
                    party_type: frm.doc.request_from,
                    party: frm.doc.party,
                },
                callback: function (r) {
                    if (r.message) {
                        frm.set_value("customer_name", r.message.customer_name || "");
                    }
                },
            });
        }
    },

    facility(frm) {
        naqel.utils.resolve_facility_configuration(frm);
    },

    service_type(frm) {
        naqel.utils.resolve_facility_configuration(frm);
    },

    territory(frm) {
        naqel.utils.resolve_facility_configuration(frm);
    },

    service_configuration(frm) {
        naqel.utils.setup_facility_uom_filter(frm);
    },

    facility_measurement(frm) {
        naqel.utils.recompute_net_facility_measurement(frm);
    },

    facility_uom(frm) {
        if (frm.doc.facility_uom) {
            naqel.utils.populate_facility_uoms(frm);
            naqel.utils.fetch_conversion_factor(frm);
        } else {
            frm.clear_table("facility_uoms");
            frm.refresh_field("facility_uoms");
            frm.set_value("conversion_factor", 1);
        }
    },
});

frappe.ui.form.on("Facility Measurement", {
    uom_value(frm) {
        naqel.utils.recompute_facility_measurement(frm);
    },
});
