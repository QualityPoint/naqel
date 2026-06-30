// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address Settings", {
    load_extraction_template(frm) {
        // Get the system default country, then fetch the matching template.
        const country = frappe.sys_defaults.country || "";

        const _apply = (country_used) => {
            frappe.call({
                method: "naqel.nq_setup.doctype.address_settings.address_settings.get_extraction_template",
                args: { country: country_used },
                callback(r) {
                    if (!r.message) return;
                    const { template, matched_country } = r.message;
                    const label = matched_country
                        ? __("Loaded template for {0}.", [matched_country])
                        : __("No template for {0}. Loaded global default.", [country_used || __("unknown country")]);

                    const _set = () => {
                        frm.set_value("address_extraction_pattern", template);
                        frappe.show_alert({ message: label, indicator: matched_country ? "green" : "yellow" });
                    };

                    if (frm.doc.address_extraction_pattern) {
                        frappe.confirm(
                            __("This will overwrite the current pattern. Continue?"),
                            _set
                        );
                    } else {
                        _set();
                    }
                },
            });
        };

        _apply(country);
    },

    fetch_coordinates_from_country(frm) {
        frappe.call({
            method: "naqel.nq_setup.doctype.address_settings.address_settings.fetch_country_coordinates",
            freeze: true,
            freeze_message: __("Fetching coordinates…"),
            callback: function (r) {
                if (!r.message) return;
                frm.set_value({
                    "default_map_latitude": r.message.latitude,
                    "default_map_longitude": r.message.longitude
                });
                frappe.show_alert({
                    message: __(
                        "Coordinates set for {0}. Save to apply.",
                        [r.message.country]
                    ),
                    indicator: "green",
                });
            },
        });
    },

    sample(frm) {
        if (!frm.doc.sample) {
            frm.set_value("sample_display", "");
        }
    },

    parse_sample(frm) {
        if (!frm.doc.sample) {
            frappe.msgprint({
                title: __("No Sample"),
                message: __("Please attach a sample document first."),
                indicator: "orange",
            });
            return;
        }

        const _doParse = function () {
            frappe.call({
                method: "naqel.nq_setup.doctype.address_settings.address_settings.parse_sample_document",
                args: { file_url: frm.doc.sample },
                freeze: true,
                freeze_message: __("Parsing sample…"),
                callback: function (r) {
                    if (!r.message) return;
                    const result = r.message;

                    frm.set_value("sample_display", result.display_html || "");

                    if (!result.success) {
                        frappe.msgprint({
                            title: __("Parsing Failed"),
                            message: result.error || __("Could not extract address fields from the sample."),
                            indicator: "orange",
                        });
                    } else {
                        frappe.show_alert({ message: __("Sample parsed successfully."), indicator: "green" });
                        if (result.warnings && result.warnings.length) {
                            frappe.msgprint({
                                title: __("Parsing Warnings"),
                                message: result.warnings.join("<br>"),
                                indicator: "yellow",
                            });
                        }
                    }
                },
            });
        };

        if (frm.is_dirty()) {
            frm.save().then(_doParse);
        } else {
            _doParse();
        }
    },
});
