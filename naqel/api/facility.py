import frappe
from frappe import _


def _get_party(email):
    from frappe.contacts.doctype.contact.contact import get_contact_name

    contact_name = get_contact_name(email)
    if not contact_name:
        return None, None

    contact = frappe.get_doc("Contact", contact_name)
    for link in contact.links:
        if link.link_doctype == "Customer":
            return "Customer", link.link_name
        if link.link_doctype == "Lead":
            return "Lead", link.link_name

    return None, None


def _get_party_facility_names(party_type, party_name):
    return frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Facility",
            "link_doctype": party_type,
            "link_name": party_name,
        },
        pluck="parent",
    )


def _check_facility_access(name, party_type, party_name):
    linked = frappe.db.exists(
        "Dynamic Link",
        {"parenttype": "Facility", "parent": name, "link_doctype": party_type, "link_name": party_name},
    )
    if not linked:
        frappe.throw(_("Facility not found"), frappe.PermissionError)


@frappe.whitelist()
def get_facilities():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        return []

    facility_names = _get_party_facility_names(party_type, party_name)
    if not facility_names:
        return []

    facilities = frappe.get_all(
        "Facility",
        filters={"name": ["in", facility_names]},
        fields=[
            "name", "facility_name", "isic_classification", "image",
            "city", "country", "building_no", "street", "district",
        ],
        order_by="modified desc",
    )

    for f in facilities:
        isic = f.get("isic_classification")
        if isic:
            f["isic_label"] = frappe.db.get_value(
                "ISIC Classification", isic, "category_name"
            ) or isic

    return facilities


@frappe.whitelist()
def get_facility(name):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    _check_facility_access(name, party_type, party_name)

    doc = frappe.get_doc("Facility", name)

    credentials = []
    for c in doc.get("credentials") or []:
        credentials.append({
            "credential_type": c.credential_type or "",
            "document_type": c.document_type or "",
            "document_number": c.document_number or "",
            "credential": c.credential or "",
            "issue_date": str(c.issue_date) if c.issue_date else "",
            "expiry_date": str(c.expiry_date) if c.expiry_date else "",
            "has_expiry_date": c.has_expiry_date or 0,
            "eligible_for_multiple_facility_branches": c.eligible_for_multiple_facility_branches or 0,
        })

    return {
        "name": doc.name,
        "facility_name": doc.facility_name or "",
        "isic_classification": doc.isic_classification or "",
        "is_group": doc.is_group or 0,
        "parent_facility": doc.parent_facility or "",
        "building_no": doc.get("building_no") or "",
        "street": doc.street or "",
        "secondary_no": doc.get("secondary_no") or "",
        "district": doc.get("district") or "",
        "city": doc.city or "",
        "postal_code": doc.pincode or "",
        "country": doc.country or "",
        "territory": doc.get("territory") or "",
        "location": doc.get("location") or "",
        "latitude": doc.get("latitude") or 0,
        "longitude": doc.get("longitude") or 0,
        "image": doc.image or "",
        "credentials": credentials,
    }


def _apply_facility_data(doc, data):
    doc.facility_name = data.get("facility_name", doc.facility_name)
    doc.isic_classification = data.get("isic_classification") or None
    doc.is_group = data.get("is_group") or 0
    doc.parent_facility = data.get("parent_facility") or None
    doc.building_no = data.get("building_no") or ""
    doc.street = data.get("street") or ""
    doc.secondary_no = data.get("secondary_no") or ""
    doc.district = data.get("district") or ""
    doc.city = data.get("city") or ""
    doc.pincode = data.get("postal_code") or ""
    doc.country = data.get("country") or None
    doc.territory = data.get("territory") or None
    doc.location = data.get("location") or None
    doc.latitude = data.get("latitude") or 0
    doc.longitude = data.get("longitude") or 0

    doc.set("credentials", [])
    for c in data.get("credentials") or []:
        doc.append("credentials", {
            "credential_type": c.get("credential_type") or None,
            "document_type": c.get("document_type") or None,
            "document_number": c.get("document_number") or "",
            "credential": c.get("credential") or None,
            "issue_date": c.get("issue_date") or None,
            "expiry_date": c.get("expiry_date") or None,
        })


@frappe.whitelist()
def create_facility(data):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if isinstance(data, str):
        import json
        data = json.loads(data)

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    doc = frappe.new_doc("Facility")
    _apply_facility_data(doc, data)
    doc.append("links", {"link_doctype": party_type, "link_name": party_name})
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()

    return {"success": True, "name": doc.name, "message": _("Facility created successfully")}


@frappe.whitelist()
def update_facility(data):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if isinstance(data, str):
        import json
        data = json.loads(data)

    name = data.get("name")
    if not name:
        frappe.throw(_("Facility name is required"))

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        frappe.throw(_("No linked Lead or Customer"))

    _check_facility_access(name, party_type, party_name)

    doc = frappe.get_doc("Facility", name)
    _apply_facility_data(doc, data)
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {"success": True, "message": _("Facility updated successfully")}


@frappe.whitelist()
def get_credential_config(lang=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if lang:
        frappe.local.lang = lang

    from naqel.utils.validations import get_credential_config as _get_config
    result = _get_config()

    config = result.get("config") or {}
    translated_config = {}
    for ct, doc_types in config.items():
        translated_config[ct] = {
            "label": _(ct),
            "document_types": doc_types,
        }
    result["config"] = translated_config
    return result


@frappe.whitelist()
def get_facility_parents():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    party_type, party_name = _get_party(frappe.session.user)
    if not party_name:
        return []

    facility_names = _get_party_facility_names(party_type, party_name)
    if not facility_names:
        return []

    return frappe.get_all(
        "Facility",
        filters={"name": ["in", facility_names], "is_group": 1},
        fields=["name", "facility_name"],
        order_by="facility_name asc",
    )


@frappe.whitelist()
def get_territory_settings():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    settings = frappe.get_cached_doc("Service Settings")
    return {
        "requires_territory": settings.requires_assigning_territory or 0,
        "division_category": settings.assigned_address_division_category or "",
    }


@frappe.whitelist()
def get_location_settings():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    settings = frappe.get_cached_doc("Address Settings")
    return {
        "requires_pinned_location": settings.requires_pinned_location or 0,
        "default_latitude": settings.get("default_map_latitude") or 24.7136,
        "default_longitude": settings.get("default_map_longitude") or 46.6753,
        "default_zoom": settings.get("default_map_zoom") or 6,
    }
