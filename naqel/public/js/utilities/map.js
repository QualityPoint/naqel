frappe.after_ajax(function () {
    frappe.call({
        method: "naqel.nq_setup.doctype.address_settings.address_settings.get_map_defaults",
        callback: function (r) {
            if (r.message) {
                frappe.utils.map_defaults.center = r.message.center;
                frappe.utils.map_defaults.zoom = r.message.zoom;
            }
        },
    });
});
