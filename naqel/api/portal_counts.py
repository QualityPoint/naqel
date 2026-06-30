import frappe
from frappe import _


@frappe.whitelist()
def get_counts():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    from naqel.api.facility import _get_party, _get_party_facility_names

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        return {"facilities": 0, "requests": 0, "quotations": 0, "contracts": 0}

    facility_names = _get_party_facility_names(party_type, party_name)
    facility_count = len(facility_names)

    request_count = 0
    quotation_count = 0
    contract_count = 0

    if facility_names:
        request_count = frappe.db.count(
            "Service Request", {"facility": ["in", facility_names]}
        )
        quotation_count = frappe.db.count(
            "Service Quotation", {"facility": ["in", facility_names]}
        )

    if party_type == "Customer":
        contract_count = frappe.db.count(
            "Service Contract", {"customer": party_name}
        )

    return {
        "facilities": facility_count,
        "requests": request_count,
        "quotations": quotation_count,
        "contracts": contract_count,
    }


@frappe.whitelist()
def get_service_types_with_counts(facility, lang=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if lang:
        frappe.local.lang = lang

    from naqel.api.facility import _get_party, _check_facility_access

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    _check_facility_access(facility, party_type, party_name)

    service_types = frappe.get_all(
        "Service Type",
        fields=["name", "service_name", "image"],
        order_by="service_name asc",
        ignore_permissions=True,
    )

    request_counts = {}
    if service_types:
        requests = frappe.get_all(
            "Service Request",
            filters={"facility": facility},
            fields=["service_type"],
            ignore_permissions=True,
        )
        for r in requests:
            request_counts[r.service_type] = request_counts.get(r.service_type, 0) + 1

    result = []
    for st in service_types:
        result.append({
            "name": st.name,
            "service_name": _(st.service_name),
            "image": st.image or "",
            "count": request_counts.get(st.name, 0),
        })

    return result


@frappe.whitelist()
def create_service_request(facility, service_type):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    from naqel.api.facility import _get_party, _check_facility_access

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    _check_facility_access(facility, party_type, party_name)

    doc = frappe.get_doc({
        "doctype": "Service Request",
        "facility": facility,
        "service_type": service_type,
        "request_from": party_type,
        "party": party_name,
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()

    return {"success": True, "name": doc.name, "message": _("Service Request created successfully")}


@frappe.whitelist()
def get_facility_connections(facility):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    from naqel.api.facility import _get_party, _check_facility_access

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    _check_facility_access(facility, party_type, party_name)

    requests = frappe.get_all(
        "Service Request",
        filters={"facility": facility},
        fields=["name", "status", "creation", "service_type"],
        order_by="creation desc",
        ignore_permissions=True,
    )

    quotations = frappe.get_all(
        "Service Quotation",
        filters={"facility": facility},
        fields=["name", "status", "creation"],
        order_by="creation desc",
        ignore_permissions=True,
    )

    contracts = []
    if party_type == "Customer":
        contracts = frappe.get_all(
            "Service Contract",
            filters={"customer": party_name},
            fields=["name", "status", "creation"],
            order_by="creation desc",
            ignore_permissions=True,
        )

    projects = frappe.get_all(
        "Operation Order",
        filters={"facility": facility},
        fields=["name", "status", "creation"],
        order_by="creation desc",
        ignore_permissions=True,
    )

    return {
        "requests": requests,
        "quotations": quotations,
        "contracts": contracts,
        "projects": projects,
    }
