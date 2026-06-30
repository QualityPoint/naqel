// Copyright (c) 2026, QuailtyPoint and contributors
// For license information, please see license.txt


frappe.ui.form.on("Service Quotation", {
	setup(frm) {
		// Restrict the party doctype to the supported party types (mirrors erpnext).
		frm.set_query("quotation_to", function () {
			return {
				filters: {
					name: ["in", ["Customer", "Lead"]]
				}
			};
		});

		// Scope party-linked address and contact pickers to the selected party
		// (link_doctype = quotation_to, link_name = party_name).
		frm.set_query("customer_address", () => party_link_query(frm));
		frm.set_query("contact_person", () => party_link_query(frm, "contact"));

		frm.set_query("facility", function () {
			return {
				filters: [
					["link_doctype", "=", frm.doc.quotation_to],
					["link_name", "=", frm.doc.party_name]
				]
			};
		});
		// Manual picker: scope to the right doctype (driven by calculation_based_on)
		// and to the facility's ISIC walk / territory ancestors via server queries.
		frm.set_query("service_configuration", function () {
			const is_regional = frm.doc.calculation_based_on === "Regional Service Configuration";
			const method = is_regional
				? "naqel.nq_crm.doctype.service_quotation.service_quotation.query_regional_service_configurations"
				: "naqel.nq_crm.doctype.service_quotation.service_quotation.query_service_configurations";
			return {
				query: method,
				filters: {
					service_type: frm.doc.service_type,
					isic_classification: frm.doc.isic_classification,
					territory: frm.doc.territory
				}
			};
		});

		// Territory is collected at the level the Service Type assigns.
		frm.set_query("territory", function () {
			const filters = {};
			if (frm.doc.assigned_address_division_category) {
				filters.division_category = frm.doc.assigned_address_division_category;
			}
			return { filters };
		});
		// Restrict company_address to addresses linked to the selected company.
		frm.set_query("company_address", function () {
			return {
				filters: [
					["link_doctype", "=", "Company"],
					["link_name", "=", frm.doc.company]
				]
			};
		});

		// Taxes table — scope account/cost-center pickers to the company (mirrors ERPNext).
		frm.set_query("account_head", "taxes", function (doc) {
			return {
				query: "erpnext.controllers.queries.tax_account_query",
				filters: {
					account_type: ["Tax", "Chargeable", "Expense Account"],
					company: doc.company
				}
			};
		});
		frm.set_query("cost_center", "taxes", function (doc) {
			return { filters: { company: doc.company, is_group: 0 } };
		});
		frm.set_query("sales_taxes_and_charges_template", function (doc) {
			return { filters: { company: doc.company, disabled: 0 } };
		});
	},

	onload(frm) {
		set_default_valid_till(frm);
	},

	refresh(frm) {
		// Tell Frappe which field/doctype the address & contact widgets are linked to.
		frappe.dynamic_link = { doc: frm.doc, fieldname: "party_name", doctype: frm.doc.quotation_to };
		set_party_labels(frm);
		setup_facility_uom_filter(frm);
		toggle_company_currency_fields(frm);

		// Disable the calculate button once the quotation is submitted.
		frm.set_df_property("calculate_service_price", "read_only", frm.doc.docstatus !== 0);

		// Create → Sales Order on a submitted quotation (mirrors ERPNext's Quotation).
		if (frm.doc.docstatus === 1 && !["Sales Order", "Cancelled", "Rejected", "Expired"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Sales Order"), () => {
				frappe.model.open_mapped_doc({
					method: "naqel.nq_crm.doctype.service_quotation.service_quotation.make_sales_order",
					frm: frm
				});
			}, __("Create"));
			frm.page.set_inner_btn_group_as_primary(__("Create"));
		}
	},

	calculate_service_price(frm) {
		// Button field: run the waste calc and rebuild the Containers table.
		if (frm.doc.docstatus !== 0) return;
		calculate_service_pricing(frm);
	},

	quotation_to(frm) {
		// Party type changed: relabel and clear the now-stale party-dependent fields.
		set_party_labels(frm);
		frm.set_value({
			party_name: "",
			customer_name: "",
			customer_address: "",
			customer_address_display: "",
			contact_person: "",
			contact_display: "",
			contact_mobile: "",
			contact_email: ""
		});
	},

	party_name(frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: "party_name", doctype: frm.doc.quotation_to };

		if (!frm.doc.quotation_to || !frm.doc.party_name) {
			frm.set_value({
				customer_name: "",
				customer_address: "",
				customer_address_display: "",
				contact_person: "",
				contact_display: "",
				contact_mobile: "",
				contact_email: ""
			});
			return;
		}

		// Fetch the party's name, default address (rendered) and default contact.
		frappe.call({
			method: "naqel.utils.utils.get_party_details",
			args: { party_type: frm.doc.quotation_to, party: frm.doc.party_name },
			callback: function (r) {
				if (!r.message) return;
				frm.updating_party_details = true;
				frappe.run_serially([
					() => frm.set_value(r.message),
					() => { frm.updating_party_details = false; }
				]);
			}
		});
	},

	customer_address(frm) {
		// Skip while party details are being applied (display already included).
		if (frm.updating_party_details) return;
		if (frm.doc.customer_address) {
			render_address_display(frm, frm.doc.customer_address, "customer_address_display");
		} else {
			frm.set_value("customer_address_display", "");
		}
	},

	contact_person(frm) {
		if (frm.updating_party_details) return;
		if (frm.doc.contact_person) {
			frappe.call({
				method: "frappe.contacts.doctype.contact.contact.get_contact_details",
				args: { contact: frm.doc.contact_person },
				callback: function (r) {
					if (r.message) frm.set_value(r.message);
				}
			});
		} else {
			frm.set_value({
				contact_display: "",
				contact_mobile: "",
				contact_email: ""
			});
		}
	},

	facility(frm) {
		render_facility_address(frm);
		resolve_configuration(frm);
	},

	service_type(frm) {
		resolve_configuration(frm);
	},

	territory(frm) {
		resolve_configuration(frm);
	},

	ignore_default_configuration(frm) {
		if (!frm.doc.ignore_default_configuration) {
			resolve_configuration(frm);
		}
	},

	service_configuration(frm) {
		naqel.utils.setup_facility_uom_filter(frm);
		if (!frm.doc.ignore_default_configuration || !frm.doc.service_configuration) return;
		warn_if_manual_deviates(frm);
	},

	facility_measurement(frm) {
		naqel.utils.recompute_net_facility_measurement(frm);
	},

	facility_uom(frm) {
		if (frm.doc.facility_uom) {
			naqel.utils.populate_facility_uoms(frm);
			naqel.utils.fetch_conversion_factor(frm);
		} else {
			frm.clear_table("facility_uoms");
			frm.refresh_field("facility_uoms");
			frm.set_value("conversion_factor", 1);
		}
	},

	company(frm) {
		// Company currency may change → re-evaluate which base fields to show.
		toggle_company_currency_fields(frm);
		if (frm.doc.company) {
			// Fetch default company address via Dynamic Link
			naqel.utils
				.get_default_address("Company", frm.doc.company)
				.then(address => frm.set_value("company_address", address || ""));
		} else {
			frm.set_value({
				company_address: "",
				company_address_display: ""
			});
		}
	},

	company_address(frm) {
		if (frm.doc.company_address) {
			render_address_display(frm, frm.doc.company_address, "company_address_display");
		} else {
			frm.set_value("company_address_display", "");
		}
	},

	currency(frm) {
		// Refresh the doc -> company-currency rate and re-derive base_* values, then
		// show/hide the company-currency fields based on whether the currencies differ.
		fetch_conversion_rate(frm);
		toggle_company_currency_fields(frm);
	},

	conversion_rate(frm) {
		// Manual rate edit re-derives every row's company-currency base_* values.
		recompute_container_base(frm);
	},

	single_collection_mechanism(frm) {
		// Bulk-apply the chosen collection mechanism to every container row
		// (mirrors "Set Target Warehouse" on ERPNext's Delivery Note).
		if (!frm.doc.single_collection_mechanism) return;
		(frm.doc.containers || []).forEach(row => {
			row.collection_mechanism = frm.doc.single_collection_mechanism;
		});
		frm.refresh_field("containers");
	},

	sales_taxes_and_charges_template(frm) {
		// Load the template's tax rows (reusing ERPNext's loader), then recompute.
		if (!frm.doc.sales_taxes_and_charges_template) {
			frm.clear_table("taxes");
			frm.refresh_field("taxes");
			calculate_taxes(frm);
			return;
		}
		frappe.call({
			method: "erpnext.controllers.accounts_controller.get_taxes_and_charges",
			args: {
				master_doctype: "Sales Taxes and Charges Template",
				master_name: frm.doc.sales_taxes_and_charges_template
			},
			callback(r) {
				if (!r.message) return;
				frm.clear_table("taxes");
				r.message.forEach(tax => {
					const row = frm.add_child("taxes");
					Object.assign(row, tax);
				});
				frm.refresh_field("taxes");
				calculate_taxes(frm);
			}
		});
	},

	start_date(frm) {
		update_contract_duration(frm);
	},

	end_date(frm) {
		update_contract_duration(frm);
	},

	duration_uom(frm) {
		update_contract_duration(frm);
	},
});

function party_link_query(frm, kind) {
	// Standard Frappe link query scoping Address/Contact to the selected party.
	const query =
		kind === "contact"
			? "frappe.contacts.doctype.contact.contact.contact_query"
			: "frappe.contacts.doctype.address.address.address_query";
	return {
		query: query,
		filters: {
			link_doctype: frm.doc.quotation_to,
			link_name: frm.doc.party_name
		}
	};
}

function set_party_labels(frm) {
	// Relabel party_name and customer_address to reflect the chosen party type,
	// e.g. "Lead" / "Lead Address" (mirrors erpnext's set_label).
	const party_type = frm.doc.quotation_to;
	if (!party_type) return;
	frm.set_df_property("party_name", "label", __(party_type));
	if (frm.fields_dict.customer_address) {
		frm.fields_dict.customer_address.set_label(__("{0} Address", [__(party_type)]));
	}
}

function set_default_valid_till(frm) {
	// Mirror erpnext's Quotation: on a brand-new quotation with no Valid Till,
	// default it to transaction_date + "Default Quotation Validity Days". The value
	// is read from frappe.boot (set in naqel/boot.py) rather than via a server call,
	// so it works for every role without a read permission on Service Settings.
	// Python (before_validate) applies the same default authoritatively on save.
	if (!frm.is_new() || frm.doc.valid_till) return;

	const days = cint(frappe.boot.sysdefaults.service_quotation_valid_till);
	const base = frm.doc.transaction_date || frappe.datetime.get_today();
	frm.set_value(
		"valid_till",
		days ? frappe.datetime.add_days(base, days) : frappe.datetime.add_months(base, 1)
	);
}

function render_facility_address(frm) {
	// Mirror Service Contract's address display: resolve the facility's default
	// linked Address (via Dynamic Link) and render it through the Address Template
	// into the facility_address field. Triggered on facility selection.
	if (!frm.doc.facility) {
		frm.set_value("facility_address", "");
		return;
	}

	naqel.utils.get_default_address("Facility", frm.doc.facility).then(address => {
		if (!address) {
			frm.set_value("facility_address", "");
			return;
		}
		frappe.call({
			method: "frappe.contacts.doctype.address.address.get_address_display",
			args: { address_dict: address },
			callback: function (d) {
				frm.set_value("facility_address", d.message || "");
			}
		});
	});
}

function render_address_display(frm, address_name, display_field) {
	// Render an Address (per the Address Template) into a display field.
	frappe.call({
		method: "frappe.contacts.doctype.address.address.get_address_display",
		args: { address_dict: address_name },
		callback: function (r) {
			frm.set_value(display_field, r.message || "");
		}
	});
}

function update_contract_duration(frm) {
	if (frm.doc.mode_of_service !== "Duration-Based") return;

	naqel.utils
		.calculate_duration(frm.doc.start_date, frm.doc.end_date, frm.doc.duration_uom)
		.then(value => frm.set_value("service_duration", value));
}

function resolve_configuration(frm) {
	// Auto mode only: ask the server for the priority-resolved configuration and
	// fill calculation_based_on (driver of the Dynamic Link) before the link itself.
	if (frm.doc.ignore_default_configuration) return;
	if (!frm.doc.service_type || !frm.doc.facility) return;

	frappe.call({
		method: "naqel.nq_crm.doctype.service_quotation.service_quotation.get_resolved_configuration",
		args: {
			service_type: frm.doc.service_type,
			facility: frm.doc.facility,
			territory: frm.doc.territory
		},
		callback: function (r) {
			if (!r.message) return;
			frappe.run_serially([
				() => frm.set_value("calculation_based_on", r.message.calculation_based_on || ""),
				() => frm.set_value("service_configuration", r.message.service_configuration || "")
			]);
		}
	});
}

function calculate_service_pricing(frm) {
	// Run the waste calculation on the resolved configuration and replace the
	// Containers table with the single suggested container (all derived fields set).
	if (!frm.doc.service_configuration) {
		frappe.msgprint(__("Resolve a Service Configuration first."));
		return;
	}

	frappe.call({
		method: "naqel.nq_crm.doctype.service_quotation.service_quotation.calculate_service_pricing",
		args: { doc: frm.doc },
		freeze: true,
		freeze_message: __("Calculating Service Pricing..."),
		callback: function (r) {
			if (r.exc || !r.message) return;

			frm.clear_table("containers");
			(r.message.containers || []).forEach(row => frm.add_child("containers", row));
			frm.refresh_field("containers");

			recompute_container_totals(frm);

			frappe.show_alert({ message: __("Service pricing calculated"), indicator: "green" });
		}
	});
}

function duration_factor(frm) {
	// Rental-length multiplier: the service duration for Duration-Based quotations.
	if (frm.doc.mode_of_service === "Duration-Based" && frm.doc.service_duration) {
		return frm.doc.service_duration;
	}
	return 1;
}

function recompute_container_row(frm, cdt, cdn) {
	// A container's count/price drive its own totals (volume / converted volume / tare),
	// its line amount (price × count × duration), and the company-currency base_* twins.
	const row = locals[cdt][cdn];
	const count = row.container_count || 0;
	const cr = frm.doc.conversion_rate || 1;
	row.total_volume = (row.volume || 0) * count;
	row.total_converted_volume = (row.converted_volume || 0) * count;
	row.total_tare_weight = (row.tare_weight || 0) * count;
	row.amount = (row.container_price || 0) * count * duration_factor(frm);
	row.base_container_price = (row.container_price || 0) * cr;
	row.base_amount = (row.amount || 0) * cr;
	frm.refresh_field("containers");
}

function recompute_container_base(frm) {
	// Re-derive every row's company-currency base_* values after a currency / rate change.
	const cr = frm.doc.conversion_rate || 1;
	(frm.doc.containers || []).forEach(row => {
		row.base_default_container_price = (row.default_container_price || 0) * cr;
		row.base_container_price = (row.container_price || 0) * cr;
		row.base_amount = (row.amount || 0) * cr;
	});
	frm.refresh_field("containers");
	recompute_container_totals(frm);
}

function recompute_container_totals(frm) {
	// Parent totals are the running sums across the Containers child table, in both the
	// document currency and the company (base) currency.
	const rows = frm.doc.containers || [];
	let count = 0, volume = 0, converted = 0, amount = 0, base_amount = 0;
	rows.forEach(row => {
		count += row.container_count || 0;
		volume += row.total_volume || 0;
		converted += row.total_converted_volume || 0;
		amount += row.amount || 0;
		base_amount += row.base_amount || 0;
	});
	frm.set_value("total_container_count", count);
	frm.set_value("total_volume", volume);
	frm.set_value("total_converted_volume", converted);
	frm.set_value("total", amount);
	frm.set_value("net_total", amount);
	frm.set_value("base_total", base_amount);
	frm.set_value("base_net_total", base_amount);

	// Taxes ride on top of the net total to produce the grand total.
	calculate_taxes(frm);
}

function calculate_taxes(frm) {
	// Mirrors ERPNext's Sales Taxes engine, scoped to our document-level model: each
	// tax row's amount is derived from its charge_type, accumulated into a running
	// total, then the grand/rounded totals are produced in both currencies.
	const net_total = frm.doc.net_total || 0;
	const base_net_total = frm.doc.base_net_total || 0;
	const cr = frm.doc.conversion_rate || 1;
	const taxes = frm.doc.taxes || [];

	let running_total = net_total;
	taxes.forEach((row, index) => {
		const rate = row.rate || 0;
		let tax_amount = 0;

		if (row.charge_type === "On Net Total") {
			tax_amount = net_total * rate / 100;
		} else if (row.charge_type === "On Previous Row Amount") {
			const ref = taxes[(row.row_id || index) - 1];
			tax_amount = (ref ? ref.tax_amount || 0 : 0) * rate / 100;
		} else if (row.charge_type === "On Previous Row Total") {
			const ref = taxes[(row.row_id || index) - 1];
			tax_amount = (ref ? ref.total || 0 : 0) * rate / 100;
		} else if (row.charge_type === "Actual") {
			tax_amount = row.tax_amount || 0; // user-entered, kept as-is
		}

		row.tax_amount = tax_amount;
		running_total += tax_amount;
		row.total = running_total;
		row.base_tax_amount = tax_amount * cr;
		row.base_total = running_total * cr;
	});
	frm.refresh_field("taxes");

	const total_taxes = net_total ? running_total - net_total : 0;
	frm.set_value("total_taxes_and_charges", total_taxes);
	frm.set_value("base_total_taxes_and_charges", total_taxes * cr);

	const grand_total = net_total + total_taxes;
	const base_grand_total = base_net_total + total_taxes * cr;
	frm.set_value("grand_total", grand_total);
	frm.set_value("base_grand_total", base_grand_total);

	const rounded = frm.doc.disable_rounded_total ? grand_total : Math.round(grand_total);
	const base_rounded = frm.doc.disable_rounded_total ? base_grand_total : Math.round(base_grand_total);
	frm.set_value("rounding_adjustment", rounded - grand_total);
	frm.set_value("rounded_total", rounded);
	frm.set_value("base_rounding_adjustment", base_rounded - base_grand_total);
	frm.set_value("base_rounded_total", base_rounded);

	set_total_in_words(frm, rounded, base_rounded);
}

function set_total_in_words(frm, total, base_total) {
	// Live spelling of the totals, using the shared app helper (SAR/Halala) — document
	// currency for in_words, company currency for base_in_words. Server recomputes the
	// same on save, so this is purely for instant feedback.
	if (frm.doc.currency) {
		frappe.call({
			method: "naqel.utils.utils.format_currency_in_words",
			args: { amount: total, currency: frm.doc.currency },
			callback(r) { frm.set_value("in_words", r.message || ""); }
		});
	} else {
		frm.set_value("in_words", "");
	}

	if (!frm.doc.company) {
		frm.set_value("base_in_words", "");
		return;
	}
	frappe.db.get_value("Company", frm.doc.company, "default_currency").then(r => {
		const company_currency = r.message && r.message.default_currency;
		if (!company_currency) {
			frm.set_value("base_in_words", "");
			return;
		}
		frappe.call({
			method: "naqel.utils.utils.format_currency_in_words",
			args: { amount: base_total, currency: company_currency },
			callback(res) { frm.set_value("base_in_words", res.message || ""); }
		});
	});
}

function toggle_company_currency_fields(frm) {
	// Show the (Company Currency) fields only when the document currency differs from
	// the company currency — mirrors ERPNext's change_form_labels / change_grid_labels.
	const parent_base = [
		"conversion_rate", "base_total", "base_net_total", "base_grand_total",
		"base_rounded_total", "base_total_taxes_and_charges", "base_discount_amount",
		"base_in_words", "base_rounding_adjustment"
	];
	const child_base = ["base_default_container_price", "base_container_price", "base_amount"];

	const apply = (company_currency) => {
		const show = !!(company_currency && frm.doc.currency && frm.doc.currency !== company_currency);
		frm.toggle_display(parent_base, show);
		const grid = frm.fields_dict.containers && frm.fields_dict.containers.grid;
		if (grid) {
			child_base.forEach(field => grid.set_column_disp(field, show));
		}
		const taxes_grid = frm.fields_dict.taxes && frm.fields_dict.taxes.grid;
		if (taxes_grid) {
			["base_tax_amount", "base_total"].forEach(field => taxes_grid.set_column_disp(field, show));
		}
	};

	if (!frm.doc.company) {
		apply(null);
		return;
	}
	frappe.db.get_value("Company", frm.doc.company, "default_currency").then(r => {
		apply(r.message && r.message.default_currency);
	});
}

function fetch_conversion_rate(frm) {
	// Resolve the document-currency → company-currency rate, then refresh base_* values.
	if (!frm.doc.currency || !frm.doc.company) return;
	frappe.call({
		method: "naqel.nq_crm.doctype.service_quotation.service_quotation.get_quotation_conversion_rate",
		args: { currency: frm.doc.currency, company: frm.doc.company, transaction_date: frm.doc.transaction_date },
		callback(r) {
			frm.set_value("conversion_rate", r.message || 1);
			recompute_container_base(frm);
		}
	});
}

function warn_if_manual_deviates(frm) {
	frappe.call({
		method: "naqel.nq_crm.doctype.service_quotation.service_quotation.get_resolved_configuration",
		args: {
			service_type: frm.doc.service_type,
			facility: frm.doc.facility,
			territory: frm.doc.territory
		},
		callback: function (r) {
			const recommended = r.message && r.message.service_configuration;
			if (recommended && frm.doc.service_configuration !== recommended) {
				frappe.msgprint({
					title: __("Manual Configuration Override"),
					indicator: "orange",
					message: __("Selected configuration {0} deviates from the recommended default {1}.", [
						frm.doc.service_configuration.bold(),
						recommended.bold()
					])
				});
			}
		}
	});
}

frappe.ui.form.on("Facility Measurement", {
	uom_value(frm) {
		naqel.utils.recompute_facility_measurement(frm);
	}
});

frappe.ui.form.on("Service Quotation Container", {
	container_count(frm, cdt, cdn) {
		// Editing a row's count re-derives its totals, then the parent sums.
		recompute_container_row(frm, cdt, cdn);
		recompute_container_totals(frm);
	},

	container_price(frm, cdt, cdn) {
		// Manual price override: re-derive amount + base values, then the parent sums.
		// default_container_price stays as the preserved calculated price.
		recompute_container_row(frm, cdt, cdn);
		recompute_container_totals(frm);
	}
});

frappe.ui.form.on("Service Quotation", {
	facility_uoms_remove(frm) {
		recompute_facility_measurement(frm);
	},

	containers_remove(frm) {
		recompute_container_totals(frm);
	},

	taxes_remove(frm) {
		calculate_taxes(frm);
	}
});

frappe.ui.form.on("Sales Taxes and Charges", {
	charge_type(frm) {
		calculate_taxes(frm);
	},
	rate(frm) {
		calculate_taxes(frm);
	},
	tax_amount(frm) {
		calculate_taxes(frm);
	},
	row_id(frm) {
		calculate_taxes(frm);
	}
});