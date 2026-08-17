// Copyright (c) 2026, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Operational Plan", {
    setup(frm) {
        frm.set_query("project", function () {
            return {
                filters: {
                    "company": frm.doc.company,
                    "customer": frm.doc.customer,
                },
            };
        });
    },

    containers(frm) {
        sync_coordinates(frm);
    },
});

function sync_coordinates(frm) {
    if (!frm.doc.containers) {
        return;
    }

    let geo_data;
    try {
        geo_data = JSON.parse(frm.doc.containers);
    } catch (e) {
        return;
    }

    const features = (geo_data && geo_data.features) || [];
    const points = features.filter(
        (f) => f.geometry && f.geometry.type === "Point"
    );

    if (!points.length) return;

    frm.clear_table("coordinates");

    points.forEach((point) => {
        // GeoJSON coordinates are [longitude, latitude]
        const [lng, lat] = point.geometry.coordinates;
        const row = frm.add_child("coordinates");
        row.latitude = lat;
        row.longitude = lng;
    });

    frm.refresh_field("coordinates");
}
