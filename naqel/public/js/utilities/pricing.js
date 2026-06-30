frappe.provide("naqel.pricing");

// Scope dimensions a Service Pricing Rule can be scoped by. Mirrors
// SCOPE_TYPES in naqel/utils/pricing.py; keep the two in sync. Used by both the
// Service Pricing Rule `items` table and the Service Settings
// `pricing_rule_priority` table.
naqel.pricing.SCOPE_TYPES = ["Address Division", "Collection Mechanism", "Company"];

// Restrict a child-table `scope_type` Link (-> DocType) field to the three
// valid scope dimensions.
//
//   naqel.pricing.set_scope_type_query(frm, "items");                 // Service Pricing Rule
//   naqel.pricing.set_scope_type_query(frm, "pricing_rule_priority"); // Service Settings
naqel.pricing.set_scope_type_query = function (frm, table_fieldname, scope_fieldname = "scope_type") {
	frm.set_query(scope_fieldname, table_fieldname, () => ({
		filters: { name: ["in", naqel.pricing.SCOPE_TYPES] },
	}));
};
