frappe.provide("naqel.filters");

naqel.filters = {
    uom_filter: function (frm, category, field) {
        frm.set_query(field, () => ({
            filters: {
                category: category
            }
        }));
    },

    isic_filter: function (frm, field, child_table) {
        const filters = {
            filters: {
                is_group: 0,
                category_classification: 'Activity'
            }
        };

        if (child_table) {
            frm.set_query(field, child_table, () => filters);
        } else {
            frm.set_query(field, () => filters);
        }
    },

    credential_filter: function (frm, field, child_table) {
        const filters = {
            filters: {
                name: ["in", ["Identification Number", "License"]]
            }
        };

        if (child_table) {
            frm.set_query(field, child_table, () => filters);
        } else {
            frm.set_query(field, () => filters);
        }
    }
};