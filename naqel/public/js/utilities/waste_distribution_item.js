// Copyright (c) 2026, QP and contributors
// For license information, please see license.txt

frappe.provide("naqel");

naqel.GET_LEAF_WASTE_TYPES_METHOD =
    "naqel.nq_setup.doctype.service_configuration.service_configuration.get_leaf_waste_types";

// how stored values are joined in the Small Text field
naqel.WASTE_ITEM_SEP = ", ";

/**
 * Simulate a "Table MultiSelect" inside a child-table row (Frappe forbids
 * grandchild tables). A `MultiSelectPills` control is hosted in an HTML field
 * and its selection is persisted to a Small Text field as a comma-joined string.
 *
 * The search dropdown is scoped to leaf descendants (is_group == 0) of the
 * row's `waste_type`. When `waste_type` is itself a leaf, only that one type
 * appears in search. The user selects manually — nothing is auto-populated.
 *
 * @param {string} child_doctype  e.g. "Waste Distribution" / "WC Facility Waste Item"
 * @param {string} grid_field     parent's table fieldname, e.g. "waste_distributions"
 * @param {Object} [opts]         field-name overrides:
 *   {string} storage_field  Small Text field holding the joined value (default "default_waste_item")
 *   {string} html_field     HTML field hosting the pills        (default "default_waste_item_html")
 *   {string} label          label shown above the pills         (default "Default Waste Item")
 */
naqel.bind_waste_item_editors = function (child_doctype, grid_field, opts) {
    const config = Object.assign(
        {
            storage_field: "default_waste_item",
            html_field: "default_waste_item_html",
            label: __("Default Waste Item"),
        },
        opts || {}
    );
    frappe.ui.form.on(child_doctype, {
        form_render(frm, cdt, cdn) {
            naqel.mount_waste_item_row(frm, cdt, cdn, grid_field, config);
        },
    });
};

naqel.mount_waste_item_row = function (frm, cdt, cdn, grid_field, config) {
    const grid_row = frm.fields_dict[grid_field]?.grid?.grid_rows_by_docname[cdn];
    if (!grid_row || !grid_row.grid_form) return;

    const field = grid_row.grid_form.fields_dict[config.html_field];
    if (!field) return;

    const $wrapper = $(field.$wrapper || field.wrapper).empty();
    $wrapper.css("padding-bottom", "var(--margin-md)");

    // Add label manually (HTML fields don't render their own)
    $('<label class="control-label" style="display:block;">')
        .text(config.label)
        .appendTo($wrapper);

    const row = locals[cdt][cdn];

    // Resolve allowed leaf names once; every get_data call chains off this
    // promise — no async race, and filtering always happens server-side.
    const leavesPromise = row.waste_type
        ? frappe.xcall(naqel.GET_LEAF_WASTE_TYPES_METHOD, { waste_type: row.waste_type })
        : Promise.resolve(null);

    const control = frappe.ui.form.make_control({
        parent: $wrapper,
        df: {
            fieldtype: "MultiSelectPills",
            fieldname: "default_waste_item_pills",
            get_data: (txt) => {
                return leavesPromise.then((leaves) => {
                    // Group with no leaf descendants — nothing to show
                    if (row.waste_type && leaves && leaves.length === 0) return [];

                    // Build array-style filters (same format as frm.set_query)
                    const filters = [["is_group", "=", 0]];
                    if (leaves && leaves.length) {
                        filters.push(["name", "in", leaves]);
                    }

                    return frappe
                        .xcall("frappe.desk.search.search_link", {
                            doctype: "Waste Type",
                            txt: txt || "",
                            filters: JSON.stringify(filters),
                        })
                        .then((results) =>
                            results.map((d) => ({
                                value: d.value,
                                label: d.label || __(d.value),
                                description: d.description,
                            }))
                        );
                });
            },
            change: () => {
                const values = control.get_values() || [];
                frappe.model.set_value(
                    cdt,
                    cdn,
                    config.storage_field,
                    values.join(naqel.WASTE_ITEM_SEP)
                );
            },
        },
        render_input: true,
        only_input: true,
    });

    // Restore a previously saved selection on re-open (no auto-population)
    const stored = (row[config.storage_field] || "")
        .split(/\s*[\n,]\s*/)
        .filter(Boolean);

    if (stored.length) {
        control.set_formatted_input(stored);
    }
};
