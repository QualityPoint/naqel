// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt

const SURVEY_ORDER_TYPE_MAP = {
	"Fill Level": "Waste Collection",
	"Issue": "Inspection",
	"Cleaning and Disinfection": "Cleaning and Disinfection"
};

const ORDER_LINK_FIELD = {
	"Fill Level": "collection_request",
	"Issue": "inspection_request",
	"Cleaning and Disinfection": "cleaning_request"
};

frappe.ui.form.on("Container Survey", {
	setup(frm) {
		frm.set_query("container", () => ({
			filters: {
				operational_status: "Deployed"
			}
		}));

		frm.set_query("fill_level", () => ({
			filters: {
				disabled: 0,
				fill_level_action: ["not in", ["Ignore"]]
			}
		}));
	},

	scan_barcode(frm) {
		const barcode = frm.doc.scan_barcode;
		if (!barcode) return;

		frappe.call({
			method: "naqel.nq_operation.doctype.container.container.scan_container_qr",
			args: { barcode },
			callback(r) {
				if (!r.message) return;
				const container = r.message;

				frm.set_value("container", container.name);
				frm.set_value("container_type", container.container_type);
				frm.set_value("scan_barcode", "");

				if (container.operational_status !== "Deployed") {
					frappe.msgprint({
						title: __("Warning"),
						indicator: "orange",
						message: __("Container {0} is currently {1}, not Deployed.", [
							container.name,
							__(container.operational_status),
						]),
					});
				}
			},
		});
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		const link_field = ORDER_LINK_FIELD[frm.doc.survey_type];
		const existing_order = frm.doc[link_field];

		if (!existing_order) {
			frm.add_custom_button(__("Create Operation Request"), () => {
				frappe.new_doc("Operation Request", {
					source_survey: frm.doc.name,
					container: frm.doc.container,
					request_type: SURVEY_ORDER_TYPE_MAP[frm.doc.survey_type]
				});
			});
		}

		if (frm.doc.collection_request) {
			frm.add_custom_button(__("Waste Collection Order"), () => {
				frappe.set_route("Form", "Operation Request", frm.doc.collection_request);
			}, __("View"));
		}
		if (frm.doc.inspection_request) {
			frm.add_custom_button(__("Inspection Order"), () => {
				frappe.set_route("Form", "Operation Request", frm.doc.inspection_request);
			}, __("View"));
		}
		if (frm.doc.cleaning_request) {
			frm.add_custom_button(__("Cleaning and Disinfection Order"), () => {
				frappe.set_route("Form", "Operation Request", frm.doc.cleaning_request);
			}, __("View"));
		}
	}
});
