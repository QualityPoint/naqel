frappe.treeview_settings["Facility"] = {
    ignore_fields: ["parent_facility"],
    get_tree_nodes: "naqel.nq_crm.doctype.facility.facility.get_children",
    breadcrumb: "Naqel",
    disable_add_node: true,
    get_tree_root: true,
    root_label: __("All Facilities"),
    toolbar: [
        { toggle_btn: true },
        {
            label: __("Edit"),
            condition: function (node) {
                return !node.is_root;
            },
            click: function (node) {
                frappe.set_route("Form", "Facility", node.data.value);
            },
        },
    ],
    menu_items: [
        {
            label: __("New Facility"),
            action: function () {
                frappe.new_doc("Facility", true);
            },
            condition: 'frappe.boot.user.can_create.indexOf("Facility") !== -1',
        },
    ],
    onload: function (treeview) {
        treeview.make_tree();
    },
};