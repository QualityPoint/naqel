frappe.ui.form.on("Daily Operational Plan", {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;

        const hasPending = frm.doc.planned_stops?.some(r => r.collection_status === "Pending");
        if (!hasPending) return;

        frm.doc.planned_stops.forEach((row, idx) => {
            if (row.collection_status !== "Pending") return;

            frm.add_custom_button(
                __("Collect Stop #{0}", [row.sequence_order]),
                () => collect_stop_dialog(frm, row, idx),
                __("Stops")
            );

            frm.add_custom_button(
                __("Skip Stop #{0}", [row.sequence_order]),
                () => skip_stop_dialog(frm, row, idx),
                __("Stops")
            );
        });
    }
});

function collect_stop_dialog(frm, row, idx) {
    const d = new frappe.ui.Dialog({
        title: __("Collect Stop #{0} — {1}", [row.sequence_order, row.container]),
        fields: [
            { label: __("Gross Weight"), fieldname: "gross_weight", fieldtype: "Float", reqd: 1 },
            { label: __("Tare Weight"), fieldname: "tare_weight", fieldtype: "Float", reqd: 1 },
            { label: __("Weighing Slip No."), fieldname: "weighing_slip_no", fieldtype: "Data" },
            { label: __("Notes"), fieldname: "notes", fieldtype: "Small Text" }
        ],
        primary_action_label: __("Mark Collected"),
        primary_action({ gross_weight, tare_weight, weighing_slip_no, notes }) {
            if (gross_weight < tare_weight) {
                frappe.msgprint(__("Gross weight cannot be less than tare weight."));
                return;
            }
            frappe.call({
                method: "collect_stop",
                doc: frm.doc,
                args: { stop_idx: idx, gross_weight, tare_weight, weighing_slip_no, notes },
                callback(r) {
                    d.hide();
                    frm.reload_doc();
                    if (r.message?.trip) {
                        frappe.show_alert({ message: __("Container Trip {0} created.", [r.message.trip]), indicator: "green" });
                    }
                }
            });
        }
    });
    d.show();
}

function skip_stop_dialog(frm, row, idx) {
    const d = new frappe.ui.Dialog({
        title: __("Skip Stop #{0} — {1}", [row.sequence_order, row.container]),
        fields: [
            { label: __("Reason"), fieldname: "skip_reason", fieldtype: "Small Text", reqd: 1 }
        ],
        primary_action_label: __("Mark Skipped"),
        primary_action({ skip_reason }) {
            frappe.call({
                method: "skip_stop",
                doc: frm.doc,
                args: { stop_idx: idx, skip_reason },
                callback() {
                    d.hide();
                    frm.reload_doc();
                }
            });
        }
    });
    d.show();
}
