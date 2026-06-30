import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

"""Shared pricing constants and helpers.

Used by both:
    - Service Settings       -> pricing_rule_priority child table (scope_type)
    - Service Pricing Rule    -> items child table (scope_type)

The scope-type list is mirrored on the client in
``naqel/public/js/utilities/pricing.js`` (``naqel.pricing.SCOPE_TYPES``); keep
the two in sync.
"""

# Scope dimensions a Service Pricing Rule can be scoped by.
SCOPE_TYPES = ("Address Division", "Collection Mechanism", "Company")

# Priority ranks for the dimension priority table (1 = highest authority).
PRIORITY_VALUES = ("1", "2", "3")


def validate_scope_rows(doc, child_table_field, scope_type_field="scope_type"):
    """Validate the shared ``scope_type`` rules for any scope child table.

    Enforces, for each row, that ``scope_type`` is one of :data:`SCOPE_TYPES`
    and that no dimension is used more than once. Returns the ordered list of
    scope-type values so callers can run table-specific checks on top.

    Args:
            doc: The parent document.
            child_table_field: Field name of the scope child table on the parent.
            scope_type_field: Field name for the scope type within each row.
    """
    scope_types = []
    for row in doc.get(child_table_field) or []:
        scope_type = row.get(scope_type_field)
        if scope_type not in SCOPE_TYPES:
            frappe.throw(
                _("Row #{0}: Scope Type must be one of: {1}. Got '{2}'.").format(
                    row.idx,
                    ", ".join(SCOPE_TYPES),
                    scope_type,
                ),
                title=_("Invalid Scope Type"),
            )
        if scope_type in scope_types:
            frappe.throw(
                _("Scope dimension '{0}' appears more than once; each may be used only once.").format(
                    scope_type
                ),
                title=_("Duplicate Scope Type"),
            )
        scope_types.append(scope_type)
    return scope_types


def assert_single_pricing_rule(top_rules):
    """Guard against an unresolvable Service Pricing Rule conflict.

    Intended for the Service Quotation resolver: call it with the rules left tied
    at the top of the precedence ranking (priority -> authority score -> division
    depth). With one rule or none it does nothing. With two or more genuinely tied
    rules the winner is ambiguous, so it raises a guided error explaining how to
    break the tie.

    The message distinguishes the safety-base case — a conflict where no priority
    lever has been pulled at all (neither a per-rule priority nor the Service
    Settings dimension priority) — from a conflict that persists despite a priority
    having been configured.

    Args:
            top_rules: the rules tied for highest precedence (list of dicts or
                    Documents exposing ``name`` and ``set_priority``).
    """
    if len(top_rules) <= 1:
        return

    names = ", ".join(row.get("name") for row in top_rules)
    rule_priority_set = any(row.get("set_priority") for row in top_rules)
    settings_priority_set = bool(
        frappe.get_all(
            "Service Pricing Rule Priority",
            filters={"parenttype": "Service Settings"},
            limit=1,
        )
    )

    if not rule_priority_set and not settings_priority_set:
        frappe.throw(
            _(
                "Multiple Service Pricing Rules match this context with equal precedence "
                "({0}), and no priority has been set to break the tie. Set the dimension "
                "Priority in Service Settings → Service Pricing Rule Priority, or "
                "enable “Set Priority” on one of these rules to resolve the conflict."
            ).format(names),
            title=_("Pricing Rule Conflict"),
        )

    frappe.throw(
        _(
            "Multiple Service Pricing Rules match this context with equal precedence "
            "({0}). Give one of them a distinct Priority, or adjust their scope, to "
            "resolve the conflict."
        ).format(names),
        title=_("Pricing Rule Conflict"),
    )


def get_division_ancestors(division_name):
    """Return Address Division names from the given node up to the root (inclusive).

    Walks the nested-set tree upward so a rule scoped to a parent division also
    matches quotations for any descendant. Used by the Service Quotation pricing
    resolver for Address Division scope matching.
    """
    if not division_name:
        return []
    result = frappe.db.get_value("Address Division", division_name, ["lft", "rgt"])
    if not result:
        return []
    lft, rgt = result
    return frappe.db.sql_list(
        "SELECT name FROM `tabAddress Division` WHERE lft <= %s AND rgt >= %s",
        (lft, rgt),
    )


# ============================================================================
# TWO-LAYER PRICING RESOLVER
# ============================================================================
# Layer 1 — Container Price (base rates). Layer 2 — Service Pricing Rule overrides.
# Layer 2 wins when matched; a miss inside it cascades into Layer 1. See
# docs/pricing/ for the full design. Rates are resolved in their NATIVE currency;
# conversion to the document currency happens at the Service Quotation.

# Collection period UOM → days, for collection-frequency factorization.
PERIOD_DAYS = {"Day": 1.0, "Week": 7.0, "Month": 365.0 / 12.0, "Year": 365.0}

# Fallback dimension weights when Service Settings → pricing_rule_priority is empty.
DEFAULT_DIMENSION_WEIGHTS = {"Address Division": 4, "Collection Mechanism": 2, "Company": 1}


def get_dimension_weights():
    """Dimension authority weights from Service Settings → Service Pricing Rule
    Priority (rank 1/2/3 → weight 4/2/1). Empty table → code defaults."""
    rows = frappe.get_all(
        "Service Pricing Rule Priority",
        filters={"parenttype": "Service Settings"},
        fields=["scope_type", "priority"],
    )
    if not rows:
        return dict(DEFAULT_DIMENSION_WEIGHTS)
    return {r.scope_type: 2 ** (3 - cint(r.priority)) for r in rows if r.scope_type}


def _collections_per_day(collection_count, period_count, period_uom):
    days = PERIOD_DAYS.get(period_uom, 1.0)
    denom = flt(period_count) * days
    if denom <= 0:
        return 0.0
    return flt(collection_count) / denom


def factorize_rate(default_price, collection_count, period_count, period_uom):
    """Scale the default rate by the collections-per-day ratio (requested / default)."""
    default_cpd = _collections_per_day(
        default_price.collection_count,
        default_price.collection_period_count,
        default_price.collection_period_uom,
    )
    if default_cpd <= 0:
        return flt(default_price.container_rate)
    factor = _collections_per_day(collection_count, period_count, period_uom) / default_cpd
    return flt(default_price.container_rate) * factor


def resolve_service_pricing_rule(service_type, address_division, company,
                                 collection_mechanism, transaction_date=None):
    """Return the winning Service Pricing Rule (frappe._dict with name, currency,
    missing_container_price_action) for the context, or None when none match.

    Survivors are ranked by (per-rule priority, authority score, division depth);
    a remaining tie is raised via assert_single_pricing_rule.
    """
    if not service_type:
        return None

    txn = getdate(transaction_date) if transaction_date else getdate()
    weights = get_dimension_weights()
    ancestors = set(get_division_ancestors(address_division)) if address_division else set()

    rules = frappe.get_all(
        "Service Pricing Rule",
        filters={"disabled": 0, "service_type": service_type},
        fields=["name", "set_priority", "priority", "valid_from", "valid_upto",
                "missing_container_price_action", "currency"],
    )

    matched = []
    for rule in rules:
        if rule.valid_from and txn < getdate(rule.valid_from):
            continue
        if rule.valid_upto and txn > getdate(rule.valid_upto):
            continue

        items = frappe.get_all(
            "Service Pricing Rule Item",
            filters={"parent": rule.name},
            fields=["scope_type", "scope"],
        )
        if not items:
            continue

        ok = True
        authority = 0
        division_depth = -1
        for item in items:
            if item.scope_type == "Address Division":
                if item.scope not in ancestors:
                    ok = False
                    break
                division_depth = max(division_depth, cint(frappe.db.get_value("Address Division", item.scope, "lft")))
            elif item.scope_type == "Company":
                if item.scope != company:
                    ok = False
                    break
            elif item.scope_type == "Collection Mechanism":
                if item.scope != collection_mechanism:
                    ok = False
                    break
            else:
                ok = False
                break
            authority += weights.get(item.scope_type, 0)

        if not ok:
            continue

        priority_score = (4 - cint(rule.priority)) if rule.set_priority else 0
        matched.append(frappe._dict({
            "name": rule.name,
            "set_priority": rule.set_priority,
            "currency": rule.currency,
            "missing_container_price_action": rule.missing_container_price_action,
            "_key": (priority_score, authority, division_depth),
        }))

    if not matched:
        return None

    matched.sort(key=lambda r: r["_key"], reverse=True)
    top_key = matched[0]["_key"]
    tied = [r for r in matched if r["_key"] == top_key]
    assert_single_pricing_rule(tied)
    return matched[0]


def _base_container_price(filters):
    rows = frappe.get_all(
        "Container Price",
        filters=filters,
        fields=["name", "container_rate", "currency", "collection_count",
                "collection_period_count", "collection_period_uom"],
        limit=1,
    )
    return rows[0] if rows else None


def _resolve_base_layer(service_type, container_type, collection_count, period_count,
                        period_uom, attempt_exact_first=True, force_warn=False):
    """Layer 1 resolution. Tries an exact Container Price config, else applies
    Service Settings → Missing Container Price Action (Factorize / Warn / Stop),
    factorizing from the is_default record. Returns (native_rate, currency)."""
    if attempt_exact_first:
        exact = _base_container_price({
            "service_type": service_type,
            "container_type": container_type,
            "collection_count": collection_count,
            "collection_period_count": period_count,
            "collection_period_uom": period_uom,
        })
        if exact:
            return flt(exact.container_rate), exact.currency

    default = _base_container_price({
        "service_type": service_type,
        "container_type": container_type,
        "is_default": 1,
    })
    if not default:
        frappe.throw(
            _("No Container Price exists for container {0} and service type {1}; pricing cannot be resolved.").format(
                frappe.bold(container_type), frappe.bold(service_type)
            ),
            title=_("Missing Container Price"),
        )

    settings_action = frappe.db.get_single_value("Service Settings", "missing_container_price_action") or "Factorize"
    if settings_action == "Stop":
        frappe.throw(
            _("No exact Container Price for container {0} at the requested collection configuration, and Missing Container Price Action is Stop.").format(
                frappe.bold(container_type)
            ),
            title=_("Missing Container Price"),
        )

    rate = factorize_rate(default, collection_count, period_count, period_uom)
    if force_warn or settings_action == "Warn":
        frappe.msgprint(
            _("Container {0}: no exact base price for this collection configuration — rate factorized from the default.").format(
                frappe.bold(container_type)
            ),
            title=_("Pricing Notice"),
            indicator="orange",
        )
    return rate, default.currency


def resolve_container_rate(service_type, container_type, address_division, company,
                           collection_mechanism, collection_count, collection_period_count,
                           collection_period_uom, transaction_date=None):
    """Resolve one container row's NATIVE rate via the two-layer cascade.
    Returns (native_rate, native_currency). Raises on Stop / unresolved."""
    collection_count = cint(collection_count) or 1
    collection_period_count = cint(collection_period_count) or 1
    collection_period_uom = collection_period_uom or "Day"

    rule = resolve_service_pricing_rule(
        service_type, address_division, company, collection_mechanism, transaction_date
    )
    if rule:
        rows = frappe.get_all(
            "Pricing Rule Container Price",
            filters={
                "service_pricing_rule": rule["name"],
                "container_type": container_type,
                "collection_count": collection_count,
                "collection_period_count": collection_period_count,
                "collection_period_uom": collection_period_uom,
            },
            fields=["container_rate", "currency"],
            limit=1,
        )
        if rows:
            return flt(rows[0].container_rate), rows[0].currency

        action = rule["missing_container_price_action"]
        if action == "Stop":
            frappe.throw(
                _("Pricing Rule {0} has no rate for container {1} at this collection configuration.").format(
                    frappe.bold(rule["name"]), frappe.bold(container_type)
                ),
                title=_("Missing Container Price"),
            )
        # Cascade into Layer 1. "Service Type Default Fallback" anchors straight on
        # the default; the others attempt an exact base match first; "Warn" notifies.
        attempt_exact = action in ("Use Matching Base Price", "Warn")
        return _resolve_base_layer(
            service_type, container_type, collection_count, collection_period_count,
            collection_period_uom, attempt_exact_first=attempt_exact, force_warn=(action == "Warn"),
        )

    # No matching rule → straight to Layer 1.
    return _resolve_base_layer(
        service_type, container_type, collection_count, collection_period_count, collection_period_uom
    )
