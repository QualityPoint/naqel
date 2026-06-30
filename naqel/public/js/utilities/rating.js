// Copyright (c) 2026, QP and contributors
// For license information, please see license.txt

frappe.provide("naqel");

// Frappe's Rating fieldtype stores a fraction of the max; none of the Naqel rating
// fields override the default of 5 stars.
naqel.RATING_MAX_STARS = 5;

// Whether fractional (e.g. 2.5) ratings are permitted, read from Service Settings.
// Cached after the first read; a settings change takes effect on the next reload.
naqel._allow_fractional_rating = null;
naqel.allow_fractional_rating = function () {
    if (naqel._allow_fractional_rating !== null) {
        return Promise.resolve(naqel._allow_fractional_rating);
    }
    return frappe.db
        .get_single_value("Service Settings", "allow_fractional_rating")
        .then((value) => {
            naqel._allow_fractional_rating = !!value;
            return naqel._allow_fractional_rating;
        });
};

// Snap a Rating value (a fraction of the max) to the nearest whole star unless
// fractional ratings are allowed. Works for a top-level field (pass frm with null
// cdt/cdn) or a child-table row (pass cdt/cdn).
naqel.enforce_whole_rating = function (frm, cdt, cdn, fieldname, max) {
    max = max || naqel.RATING_MAX_STARS;
    const doc = cdt && cdn ? locals[cdt][cdn] : frm.doc;
    const value = doc && doc[fieldname];
    if (!value) return;

    naqel.allow_fractional_rating().then((allowed) => {
        if (allowed) return;
        const rounded = Math.round(value * max) / max;
        if (rounded === value) return;
        if (cdt && cdn) {
            frappe.model.set_value(cdt, cdn, fieldname, rounded);
        } else {
            frm.set_value(fieldname, rounded);
        }
    });
};

// Enforce whole-star thresholds in the Rating Classification rows shared by both
// Service Configuration and Regional Service Configuration.
frappe.ui.form.on("Rating Classification", {
    rating(frm, cdt, cdn) {
        naqel.enforce_whole_rating(frm, cdt, cdn, "rating");
    },
});
