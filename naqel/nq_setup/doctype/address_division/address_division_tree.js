// Copyright (c) 2026, QualityPoint and contributors
// For license information, please see license.txt

frappe.treeview_settings["Address Division"] = {
    get_tree_nodes: "naqel.nq_setup.doctype.address_division.address_division.get_children",
    add_tree_node: "naqel.nq_setup.doctype.address_division.address_division.add_node",
    filters: [
        {
            fieldname: "country",
            fieldtype: "Link",
            options: "Country",
            label: __("Country"),
            default: frappe.defaults.get_default("country"),
        }
    ],
    breadcrumb: "Operation",
    get_tree_root: false,
    onload: function (treeview) {
        frappe.treeview_settings["Address Division"].treeview = treeview;
    },
    extend_toolbar: true,
    toolbar: [
        {
            label: __("Add Child"),
            condition: function (node) {
                return node.expandable &&
                    frappe.boot.user.can_create.indexOf("Address Division") !== -1;
            },
            click: function (node) {
                frappe.call({
                    method: "naqel.nq_setup.doctype.address_division.address_division.get_child_node_info",
                    args: { parent: node.data.value },
                    callback(r) {
                        if (!r.message) return;
                        const { country, child_division_types } = r.message;

                        const division_category_field = child_division_types.length === 1
                            ? {
                                fieldname: "division_category",
                                fieldtype: "Data",
                                label: __("Division Category"),
                                read_only: 1,
                                default: child_division_types[0],
                            }
                            : {
                                fieldname: "division_category",
                                fieldtype: "Select",
                                label: __("Division Category"),
                                options: child_division_types.join("\n"),
                                reqd: 1,
                            };

                        const d = new frappe.ui.Dialog({
                            title: __("New Address Division"),
                            fields: [
                                {
                                    fieldname: "division_name",
                                    fieldtype: "Data",
                                    label: __("Division Name"),
                                    reqd: 1,
                                },
                                division_category_field,
                                {
                                    fieldname: "parent_division",
                                    fieldtype: "Link",
                                    options: "Address Division",
                                    label: __("Parent Division"),
                                    read_only: 1,
                                    default: node.data.value,
                                },
                                {
                                    fieldname: "country",
                                    fieldtype: "Link",
                                    options: "Country",
                                    label: __("Country"),
                                    read_only: 1,
                                    default: country,
                                }
                            ],
                        });

                        d.set_primary_action(__("Create"), function () {
                            const values = d.get_values();
                            if (!values) return;
                            values.parent = node.data.value;
                            frappe.dom.freeze(__("Creating..."));
                            frappe.call({
                                method: "naqel.nq_setup.doctype.address_division.address_division.add_node",
                                args: values,
                                callback(r) {
                                    if (!r.exc) {
                                        frappe.views.trees["Address Division"].tree.load_children(node, true);
                                    }
                                },
                                always() {
                                    frappe.dom.unfreeze();
                                    d.hide();
                                },
                            });
                        });

                        d.show();
                    },
                });
            },
            btnClass: "hidden-xs",
        },
        {
            label: __("Edit"),
            condition: function (node) {
                return !node.is_root;
            },
            click: function (node) {
                frappe.set_route("Form", "Address Division", node.data.value);
            },
        },
    ],
    menu_items: [
        {
            label: __("New Address Division"),
            action: function () {
                frappe.new_doc("Address Division", true);
            },
            condition: 'frappe.boot.user.can_create.indexOf("Address Division") !== -1',
        },
    ],
};
