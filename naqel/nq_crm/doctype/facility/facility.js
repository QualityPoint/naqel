// Copyright (c) 2025, QualityPoint and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facility", {
	setup: function (frm) {
		naqel.filters.isic_filter(frm, "isic_classification");

		frm.set_query("link_doctype", "links", function () {
			return {
				filters: {
					name: ["in", ["Customer", "Lead"]]
				}
			};
		});

		frm.set_query("parent_facility", function (doc) {
			return {
				filters: {
					is_group: 1,
					party_type: doc.party_type,
					party: doc.party,
					name: ["!=", doc.name]
				},
			};
		});

		// Territory assignment is governed globally by Service Settings. Filter the
		// Territory picker to the configured Address Division category (read from the
		// read-only mirror field populated below / on server validate).
		frm.set_query("territory", function (doc) {
			const filters = {};
			if (doc.address_division_category) {
				filters.division_category = doc.address_division_category;
			}
			if (doc.country) {
				filters.country = doc.country;
			}
			return { filters };
		});

		// Base restriction on credential types (Identification Number / License),
		// shared with Service Settings. When credentials are required AND configured,
		// the async callback below narrows credential_type further to the configured set.
		naqel.filters.credential_filter(frm, "credential_type", "credentials");

		frappe.call({
			method: "naqel.utils.validations.get_credential_config",
			callback: function (r) {
				const policy = r.message || {};
				frm._credential_config = policy.config || {};
				frm._credentials_required = !!policy.required;

				// Credentials are only governed when Service Settings requires them.
				if (!frm._credentials_required) {
					return;
				}

				// Required, but the allowed types haven't been configured yet.
				if (!Object.keys(frm._credential_config).length) {
					frappe.msgprint({
						title: __("Configuration Required"),
						message: __("No credentials are configured. Please set up the allowed credential types in {0} before proceeding.", [
							`<a href="/app/service-settings">${__("Service Settings")}</a>`
						]),
						indicator: "orange",
					});
					return;
				}

				frm.set_query("credential_type", "credentials", () => ({
					filters: { name: ["in", Object.keys(frm._credential_config)] },
				}));

				frm.set_query("document_type", "credentials", function (doc, cdt, cdn) {
					const row = locals[cdt][cdn];
					const allowed = (frm._credential_config[row.credential_type] || []);
					return { filters: { name: ["in", allowed] } };
				});
			},
		});
	},

	onload: function (frm) {
		apply_territory_settings(frm);
	},

	refresh: function (frm) {
		if (!frm.doc.__islocal) {
			frappe.contacts.render_address_and_contact(frm);
			render_linked_address_buttons(frm);

			// Create → Quotation: spin up a Service Quotation pre-filled from this facility.
			frm.add_custom_button(__("Quotation"), () => {
				frappe.model.open_mapped_doc({
					method: "naqel.nq_crm.doctype.facility.facility.make_service_quotation",
					frm: frm,
				});
			}, __("Create"));
		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}
	},

	// A territory is country-scoped; clear it when the country changes so a stale
	// out-of-country Address Division can't survive the territory filter.
	country: function (frm) {
		if (frm.doc.territory) {
			frm.set_value("territory", null);
		}
	},

	// Sync geolocation to float fields when location changes (including "Clear All")
	location: function (frm) {
		naqel.geolocation.sync_geolocation_to_floats(frm, 'location', 'latitude', 'longitude');
	},

	// Sync float fields to geolocation when latitude changes
	latitude: function (frm) {
		if (frm.doc.latitude != null && frm.doc.longitude != null) {
			naqel.geolocation.sync_floats_to_geolocation(frm, 'latitude', 'longitude', 'location');
		}
	},

	// Sync float fields to geolocation when longitude changes
	longitude: function (frm) {
		if (frm.doc.latitude != null && frm.doc.longitude != null) {
			naqel.geolocation.sync_floats_to_geolocation(frm, 'latitude', 'longitude', 'location');
		}
	},

	parent_facility: function (frm) {
		frm.clear_table("credentials");
		frm.refresh_field("credentials");

		if (!frm.doc.parent_facility) return;

		frappe.call({
			method: "naqel.nq_crm.doctype.facility.facility.get_eligible_parent_credentials",
			args: {
				parent_facility: frm.doc.parent_facility
			},
			callback: function (r) {
				if (!r.message || !r.message.length) return;
				r.message.forEach(function (cred) {
					const row = frm.add_child("credentials");
					row.credential_type = cred.credential_type;
					row.document_type = cred.document_type;
					row.document_number = cred.document_number;
					row.has_expiry_date = cred.has_expiry_date;
					row.eligible_for_multiple_facility_branches = cred.eligible_for_multiple_facility_branches;
				});
				frm.refresh_field("credentials");
			},
		});
	}
});

function apply_territory_settings(frm) {
	// Mirror the global Service Settings territory policy onto the (read-only)
	// Facility fields and make Territory required in the UI when enabled. The
	// server re-applies and enforces this in validate(); this is for UX only.
	frappe.db
		.get_value("Service Settings", "Service Settings", [
			"requires_assigning_territory",
			"assigned_address_division_category",
		])
		.then(({ message }) => {
			if (!message) return;
			const requires = message.requires_assigning_territory || 0;

			// Required-flag is safe to apply on every load — it's UI-only.
			frm.set_df_property("territory", "reqd", requires ? 1 : 0);

			// Only seed the read-only mirrors on a NEW facility. The server
			// re-applies them on save (the source of truth); writing them here on
			// an already-saved doc would mark it dirty if Service Settings changed
			// since it was last saved.
			if (!frm.is_new()) return;
			frm.set_value("assign_territory", requires);
			frm.set_value(
				"address_division_category",
				requires ? message.assigned_address_division_category : ""
			);
		});
}

function render_linked_address_buttons(frm) {
	// Mirror the Contact doctype's "Links" button group: add one button per linked
	// Address (loaded via load_address_and_contact → __onload.addr_list), each
	// routing to that Address form.
	const addr_list = (frm.doc.__onload && frm.doc.__onload.addr_list) || [];
	for (const addr of addr_list) {
		frm.add_custom_button(
			__("{0}: {1}", [__("Address"), __(addr.name)]),
			function () {
				frappe.set_route("Form", "Address", addr.name);
			},
			__("Links")
		);
	}
}

frappe.ui.form.on("Dynamic Link", {
	link_name(frm, cdt, cdn) {
		const child = locals[cdt][cdn];
		if (child.link_name) {
			frappe.model.with_doctype(child.link_doctype, function () {
				const title_field = frappe.get_meta(child.link_doctype).title_field || "name";
				frappe.model.get_value(
					child.link_doctype,
					child.link_name,
					title_field,
					function (r) {
						frappe.model.set_value(cdt, cdn, "link_title", r[title_field]);
					}
				);
			});
		}
	},
});

frappe.ui.form.on("Facility Credential", {
	credential_type: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "document_type", null);
		frappe.model.set_value(cdt, cdn, "has_expiry_date", 0);
		frappe.model.set_value(cdt, cdn, "eligible_for_multiple_facility_branches", 0);
	},

	document_type: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.credential_type || !row.document_type) return;

		frappe.db.get_value(
			row.credential_type,
			row.document_type,
			["has_expiry_date", "eligible_for_multiple_facility_branches"],
			function (value) {
				if (!value) return;
				frappe.model.set_value(cdt, cdn, "has_expiry_date", value.has_expiry_date || 0);
				frappe.model.set_value(cdt, cdn, "eligible_for_multiple_facility_branches", value.eligible_for_multiple_facility_branches || 0);
			}
		);
	},

	credential: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.credential || !row.credential_type || !row.document_type) return;

		frappe.call({
			method: "naqel.utils.document_parser.api.parse_credential_document",
			args: {
				file_url: row.credential,
				credential_type: row.credential_type,
				document_type: row.document_type,
			},
			freeze: true,
			freeze_message: __("Parsing document…"),
			callback: function (r) {
				if (!r.message) return;
				const result = r.message;

				if (result.document_number) {
					frappe.model.set_value(cdt, cdn, "document_number", result.document_number);
				}
				if (result.display_html) {
					frappe.model.set_value(cdt, cdn, "document_display", result.display_html);
				}

				if (!result.success) {
					frappe.msgprint({
						title: __("Document Parsing"),
						message: result.error || __("Could not extract document number."),
						indicator: "orange",
					});
				} else if (result.warnings && result.warnings.length) {
					frappe.msgprint({
						title: __("Document Parsing — Warnings"),
						message: result.warnings.join("<br>"),
						indicator: "yellow",
					});
				}
			},
		});
	},
});
