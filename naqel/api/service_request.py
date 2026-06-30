import frappe
from frappe import _


@frappe.whitelist()
def get_service_requests(service_type=None, facility=None, status=None, lang=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if lang:
        frappe.local.lang = lang

    from naqel.api.facility import _get_party, _get_party_facility_names

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        return []

    facility_names = _get_party_facility_names(party_type, party_name)
    if not facility_names:
        return []

    if facility:
        if facility not in facility_names:
            return []
        filters = {"facility": facility}
    else:
        filters = {"facility": ["in", facility_names]}

    if service_type:
        filters["service_type"] = service_type
    if status:
        filters["status"] = status

    requests = frappe.get_all(
        "Service Request",
        filters=filters,
        fields=["name", "title", "service_type", "facility", "status", "creation"],
        order_by="creation desc",
        ignore_permissions=True,
    )

    for r in requests:
        r["service_type_label"] = _(r.service_type) if r.service_type else ""
        r["facility_name"] = frappe.db.get_value("Facility", r.facility, "facility_name") or r.facility if r.facility else ""
        r["status_label"] = _(r.status) if r.status else ""

    return requests


@frappe.whitelist()
def get_filter_options(lang=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if lang:
        frappe.local.lang = lang

    from naqel.api.facility import _get_party, _get_party_facility_names

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        return {"service_types": [], "facilities": [], "statuses": []}

    facility_names = _get_party_facility_names(party_type, party_name)

    service_types = frappe.get_all(
        "Service Type",
        fields=["name", "service_name"],
        order_by="service_name asc",
        ignore_permissions=True,
    )

    facilities = []
    if facility_names:
        facilities = frappe.get_all(
            "Facility",
            filters={"name": ["in", facility_names]},
            fields=["name", "facility_name"],
            order_by="facility_name asc",
        )

    statuses = [
        "Draft", "Under Process", "Require Clarification", "Clarified",
        "Cleared", "Quotation", "Rejected", "Cancelled",
    ]

    return {
        "service_types": [{"value": st.name, "label": _(st.service_name)} for st in service_types],
        "facilities": [{"value": f.name, "label": f.facility_name} for f in facilities],
        "statuses": [{"value": s, "label": _(s)} for s in statuses],
    }
