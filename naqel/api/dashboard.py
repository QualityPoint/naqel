# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt
"""Service Dashboard backend.

A single whitelisted endpoint (`get_service_dashboard`) aggregates org-wide
insight across the CRM/sales lifecycle — Leads, Customers, Facilities, Service
Requests, Service Quotations and Service Contracts — into one payload the Vue
dashboard renders. The page is role-gated (System Manager / Sales Manager /
Sales User) and shows all data; aggregation therefore uses `frappe.db` directly.

Filters (all optional): from_date, to_date, company, service_type, territory.
- Company applies only where the field exists (Service Quotation, Service Contract).
- Service Type applies to Service Request / Quotation / Contract.
- Territory is an Address Division subtree (nested set); it applies to every
  doctype that carries a territory, and to Contracts via their linked Quotation.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

# Roles allowed to view the dashboard (defense-in-depth; the Page is also gated).
ALLOWED_ROLES = ("System Manager", "Sales Manager", "Sales User")

# Quotation statuses that represent live pipeline (not won/lost/dead).
PIPELINE_STATUSES = ("Open", "Accepted")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_service_dashboard(filters=None):
    """Return the full dashboard payload for the given filters."""
    if not set(ALLOWED_ROLES) & set(frappe.get_roles()):
        frappe.throw(_("Not permitted to view the Service Dashboard."), frappe.PermissionError)

    f = _parse_filters(filters)

    return {
        "kpis": _kpis(f),
        "funnel": _funnel(f),
        "revenue_trend": _revenue_trend(f),
        "collections": _collections(f),
        "status": _status_breakdowns(f),
        "geography": _geography(f),
        "top": _top_lists(f),
        "filters_applied": {
            "from_date": f.from_date,
            "to_date": f.to_date,
            "company": f.company,
            "service_type": f.service_type,
            "territory": f.territory,
            "currency": f.currency,
        },
    }


# ---------------------------------------------------------------------------
# Filter parsing & shared helpers
# ---------------------------------------------------------------------------

def _parse_filters(filters):
    if isinstance(filters, str):
        filters = json.loads(filters or "{}")
    f = frappe._dict(filters or {})

    f.from_date = getdate(f.from_date) if f.get("from_date") else None
    f.to_date = getdate(f.to_date) if f.get("to_date") else None

    # Resolve the territory subtree once (list of Address Division names). Service
    # Contracts carry neither territory nor service_type directly, so both are folded
    # — via the linked Quotation — into a precomputed set of matching contract names.
    f._territories = _territory_descendants(f.get("territory"))
    f._contract_names = _contracts_matching(f._territories, f.get("service_type"))

    # Display currency: the chosen company's default, else the system default.
    f.currency = (
        frappe.get_cached_value("Company", f.company, "default_currency")
        if f.get("company")
        else frappe.db.get_default("currency")
    ) or "SAR"
    return f


def _territory_descendants(territory):
    """All Address Division names in the selected territory's subtree, or None."""
    if not territory:
        return None
    node = frappe.db.get_value("Address Division", territory, ["lft", "rgt"], as_dict=True)
    if not node:
        return [territory]
    return frappe.db.get_all(
        "Address Division",
        filters={"lft": [">=", node.lft], "rgt": ["<=", node.rgt]},
        pluck="name",
    ) or [territory]


def _contracts_matching(territories, service_type):
    """Service Contract names whose linked Quotation matches the territory subtree
    and/or the service type.

    Returns None when neither filter is active ("no restriction"). An empty list
    means a filter is active but matches nothing.
    """
    if territories is None and not service_type:
        return None

    conds, params = [], []
    if territories is not None:
        if not territories:
            return []
        conds.append(f"sq.territory IN ({', '.join(['%s'] * len(territories))})")
        params += list(territories)
    if service_type:
        conds.append("sq.service_type = %s")
        params.append(service_type)

    return frappe.db.sql_list(
        f"""
        SELECT sc.name
        FROM `tabService Contract` sc
        JOIN `tabService Quotation` sq ON sq.name = sc.service_quotation
        WHERE {' AND '.join(conds)}
        """,
        params,
    )


def _filters_for(f, date_field, *, company=False, service_type=False,
                 territory=False, territory_field="territory", contract=False):
    """Build a Frappe filters list honouring only the dimensions a doctype supports."""
    out = []
    if f.from_date and f.to_date:
        # Span the full end day — `creation`/`transaction_date` are datetimes, so a bare
        # `to_date` would compare against 00:00:00 and drop records made later that day.
        out.append([date_field, "between", [f"{f.from_date} 00:00:00", f"{f.to_date} 23:59:59"]])
    if company and f.company:
        out.append(["company", "=", f.company])
    if contract:
        # Contracts carry no territory/service_type column — both are folded into the
        # precomputed matching-name set (via the linked Quotation).
        if f._contract_names is not None:
            out.append(["name", "in", f._contract_names])
        return out
    if service_type and f.service_type:
        out.append(["service_type", "=", f.service_type])
    if territory and f._territories is not None:
        out.append([territory_field, "in", f._territories])
    return out


def _compile(filters):
    """Compile a list of ``[field, op, value]`` conditions into ``(where_sql, params)``.

    Field names are internal constants; every user-supplied value is bound as a
    parameter, so this is injection-safe. Frappe's current query builder rejects
    SQL-function strings in get_all SELECTs, so the aggregate helpers below run
    parameterized raw SQL instead.
    """
    clauses, params = [], []
    for field, op, value in filters:
        col = f"`{field}`"
        if op == "between":
            clauses.append(f"{col} BETWEEN %s AND %s")
            params.extend(value)
        elif op == "in":
            if not value:
                clauses.append("1=0")
            else:
                clauses.append(f"{col} IN ({', '.join(['%s'] * len(value))})")
                params.extend(value)
        elif op == "is" and value == "set":
            clauses.append(f"({col} IS NOT NULL AND {col} != '')")
        elif op == "!=":
            clauses.append(f"{col} != %s")
            params.append(value)
        else:  # "="
            clauses.append(f"{col} = %s")
            params.append(value)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _count(doctype, filters):
    where, params = _compile(filters)
    return frappe.db.sql(f"SELECT COUNT(*) FROM `tab{doctype}`{where}", params)[0][0]


def _sum(doctype, field, filters):
    where, params = _compile(filters)
    row = frappe.db.sql(f"SELECT COALESCE(SUM(`{field}`), 0) FROM `tab{doctype}`{where}", params)
    return flt(row[0][0])


def _group_count(doctype, group_field, filters, amount_field=None):
    """Grouped counts (and optional amount sum) → [{name, value, amount}]."""
    where, params = _compile(filters)
    amt = f", COALESCE(SUM(`{amount_field}`), 0) as amount" if amount_field else ""
    rows = frappe.db.sql(
        f"""
        SELECT `{group_field}` as name, COUNT(*) as value{amt}
        FROM `tab{doctype}`{where}
        GROUP BY `{group_field}`
        ORDER BY value DESC
        """,
        params,
        as_dict=True,
    )
    return [r for r in rows if r.get("name")]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _kpis(f):
    # Counts per doctype, each filtered on the dimensions it actually carries.
    leads = _count("Lead", _filters_for(f, "creation", territory=True))
    customers = _count("Customer", _filters_for(f, "creation", territory=True))
    facilities = _count("Facility", _filters_for(f, "creation", territory=True))
    service_requests = _count("Service Request", _filters_for(f, "creation", service_type=True, territory=True))
    quotations = _count("Service Quotation", _filters_for(f, "transaction_date", company=True, service_type=True, territory=True))

    contract_base = _filters_for(f, "contract_date", company=True, service_type=True, contract=True)
    contracts = _count("Service Contract", contract_base)
    active_contracts = _count("Service Contract", contract_base + [["status", "=", "Active"]])

    # Customers converted from a Lead (erpnext sets Customer.lead_name on conversion).
    converted = _count("Customer", _filters_for(f, "creation", territory=True) + [["lead_name", "is", "set"]])

    # Money. Contracted = submitted contracts' net_total; pipeline = live quotations'
    # grand_total; collections derived from net_total vs amount_due.
    submitted_contracts = contract_base + [["docstatus", "=", 1]]
    contracted_revenue = _sum("Service Contract", "net_total", submitted_contracts)
    outstanding = _sum("Service Contract", "amount_due", submitted_contracts)
    collected = max(contracted_revenue - outstanding, 0.0)

    pipeline_filters = _filters_for(f, "transaction_date", company=True, service_type=True, territory=True)
    pipeline_filters += [["docstatus", "=", 1], ["status", "in", list(PIPELINE_STATUSES)]]
    pipeline_value = _sum("Service Quotation", "grand_total", pipeline_filters)

    return {
        "leads": leads,
        "customers": customers,
        "customers_converted": converted,
        "facilities": facilities,
        "service_requests": service_requests,
        "quotations": quotations,
        "contracts": contracts,
        "active_contracts": active_contracts,
        "contracted_revenue": contracted_revenue,
        "pipeline_value": pipeline_value,
        "collected": collected,
        "outstanding": outstanding,
        "lead_to_customer_conversion": _pct(converted, leads),
        "sq_to_sc_conversion": _pct(contracts, quotations),
        "currency": f.currency,
    }


def _funnel(f):
    leads = _count("Lead", _filters_for(f, "creation", territory=True))
    customers = _count("Customer", _filters_for(f, "creation", territory=True))
    service_requests = _count("Service Request", _filters_for(f, "creation", service_type=True, territory=True))
    quotations = _count("Service Quotation", _filters_for(f, "transaction_date", company=True, service_type=True, territory=True))
    contracts = _count("Service Contract", _filters_for(f, "contract_date", company=True, service_type=True, contract=True))
    return [
        {"stage": _("Leads"), "value": leads},
        {"stage": _("Customers"), "value": customers},
        {"stage": _("Service Requests"), "value": service_requests},
        {"stage": _("Quotations"), "value": quotations},
        {"stage": _("Contracts"), "value": contracts},
    ]


def _revenue_trend(f):
    """Monthly contracted revenue (Service Contract) vs pipeline (Service Quotation)."""
    contracted = _monthly_sum(
        "Service Contract", "contract_date", "net_total",
        _filters_for(f, "contract_date", company=True, service_type=True, contract=True)
        + [["docstatus", "=", 1]],
    )
    pipeline = _monthly_sum(
        "Service Quotation", "transaction_date", "grand_total",
        _filters_for(f, "transaction_date", company=True, service_type=True, territory=True)
        + [["docstatus", "=", 1], ["status", "in", list(PIPELINE_STATUSES)]],
    )
    months = sorted(set(contracted) | set(pipeline))
    return [
        {"month": m, "contracted": flt(contracted.get(m, 0)), "pipeline": flt(pipeline.get(m, 0))}
        for m in months
    ]


def _monthly_sum(doctype, date_field, amount_field, filters):
    # Bucket in Python (avoids DATE_FORMAT %-escaping pitfalls).
    where, params = _compile(filters)
    rows = frappe.db.sql(
        f"SELECT `{date_field}` as d, `{amount_field}` as amt FROM `tab{doctype}`{where}",
        params,
        as_dict=True,
    )
    out = {}
    for r in rows:
        if not r.d:
            continue
        month = getdate(r.d).strftime("%Y-%m")
        out[month] = out.get(month, 0.0) + flt(r.amt)
    return out


def _collections(f):
    base = _filters_for(f, "contract_date", company=True, service_type=True, contract=True) + [["docstatus", "=", 1]]
    net = _sum("Service Contract", "net_total", base)
    outstanding = _sum("Service Contract", "amount_due", base)
    return {
        "collected": max(net - outstanding, 0.0),
        "outstanding": outstanding,
        "by_status": _group_count("Service Contract", "payment_status", base, amount_field="net_total"),
    }


def _status_breakdowns(f):
    return {
        "lead": _group_count("Lead", "status", _filters_for(f, "creation", territory=True)),
        # Customers have no status; customer_type (Company/Individual) is the always-set
        # categorical parallel (customer_group is optional and often blank).
        "customer_type": _group_count("Customer", "customer_type", _filters_for(f, "creation", territory=True)),
        "service_request": _group_count(
            "Service Request", "status",
            _filters_for(f, "creation", service_type=True, territory=True)),
        "quotation": _group_count(
            "Service Quotation", "status",
            _filters_for(f, "transaction_date", company=True, service_type=True, territory=True)),
        "contract": _group_count(
            "Service Contract", "status",
            _filters_for(f, "contract_date", company=True, service_type=True, contract=True)),
        "payment": _group_count(
            "Service Contract", "payment_status",
            _filters_for(f, "contract_date", company=True, service_type=True, contract=True)),
    }


def _geography(f):
    fac_filters = _filters_for(f, "creation", territory=True)
    return {
        "by_territory": _group_count("Facility", "territory", fac_filters),
        "by_country": _group_count("Facility", "country", fac_filters),
        "by_city": _group_count("Facility", "city", fac_filters)[:15],
        "map_points": _map_points(f, fac_filters),
    }


def _map_points(f, fac_filters):
    """Facilities with coordinates, for the Leaflet map."""
    where, params = _compile(fac_filters + [["latitude", "!=", 0], ["longitude", "!=", 0]])
    rows = frappe.db.sql(
        f"""
        SELECT name, facility_name, latitude, longitude, territory, city, rating
        FROM `tabFacility`{where}
        LIMIT 2000
        """,
        params,
        as_dict=True,
    )
    return [
        {
            "name": r.name,
            "label": r.facility_name or r.name,
            "lat": flt(r.latitude),
            "lng": flt(r.longitude),
            "territory": r.territory,
            "city": r.city,
            "rating": r.rating,
        }
        for r in rows
        if flt(r.latitude) and flt(r.longitude)
    ]


def _top_lists(f):
    contract_base = _filters_for(f, "contract_date", company=True, service_type=True, contract=True) + [["docstatus", "=", 1]]
    where, params = _compile(contract_base)

    top_customers = frappe.db.sql(
        f"""
        SELECT customer as id, customer_name as name,
               COUNT(name) as contracts, COALESCE(SUM(net_total), 0) as revenue
        FROM `tabService Contract`{where}
        GROUP BY customer ORDER BY revenue DESC LIMIT 10
        """,
        params,
        as_dict=True,
    )

    # Service type lives on the linked Quotation, not the Contract → join for it.
    join_where, join_params = _contract_join_where(f)
    top_service_types = frappe.db.sql(
        f"""
        SELECT sq.service_type as id, sq.service_type as name,
               COUNT(sc.name) as contracts, COALESCE(SUM(sc.net_total), 0) as revenue
        FROM `tabService Contract` sc
        JOIN `tabService Quotation` sq ON sq.name = sc.service_quotation
        {join_where}
        GROUP BY sq.service_type ORDER BY revenue DESC LIMIT 10
        """,
        join_params,
        as_dict=True,
    )

    return {
        "customers": [r for r in top_customers if r.get("id")],
        "service_types": [r for r in top_service_types if r.get("id")],
    }


def _contract_join_where(f):
    """WHERE for a Service Contract ⋈ Service Quotation join (table-qualified),
    used where the Contract needs its Quotation's service_type / territory."""
    conds, params = ["sc.docstatus = 1"], []
    if f.from_date and f.to_date:
        conds.append("sc.contract_date BETWEEN %s AND %s")
        params += [f"{f.from_date} 00:00:00", f"{f.to_date} 23:59:59"]
    if f.company:
        conds.append("sc.company = %s")
        params.append(f.company)
    if f.service_type:
        conds.append("sq.service_type = %s")
        params.append(f.service_type)
    if f._territories is not None:
        if not f._territories:
            conds.append("1=0")
        else:
            conds.append(f"sq.territory IN ({', '.join(['%s'] * len(f._territories))})")
            params += list(f._territories)
    return " WHERE " + " AND ".join(conds), params


def _pct(part, whole):
    return round((flt(part) / flt(whole) * 100.0), 1) if whole else 0.0


# ---------------------------------------------------------------------------
# Filter option helpers (for the toolbar)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_dashboard_filter_options():
    """Bootstrap data for the toolbar selects: companies, service types, territories."""
    if not set(ALLOWED_ROLES) & set(frappe.get_roles()):
        frappe.throw(_("Not permitted."), frappe.PermissionError)

    return {
        "companies": frappe.db.get_all("Company", fields=["name", "default_currency"], order_by="name"),
        "service_types": frappe.db.get_all("Service Type", fields=["name", "service_name"], order_by="service_name"),
        "territories": frappe.db.get_all(
            "Address Division",
            fields=["name", "division_name", "division_category", "is_group"],
            order_by="lft",
        ),
        "today": nowdate(),
    }
