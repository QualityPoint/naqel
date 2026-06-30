import frappe
from frappe import _


def _get_linked_doc(email):
    """Return (doctype, name) for the Lead or Customer linked to the logged-in user's Contact."""
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


def _get_linked_address(doctype, name):
    """Return the primary Address linked to a Lead or Customer, or None."""
    from frappe.contacts.doctype.address.address import get_default_address

    address_name = get_default_address(doctype, name)
    if not address_name:
        return None
    return frappe.get_doc("Address", address_name)


def _address_to_dict(addr):
    """Extract address fields from an Address doc into a flat dict."""
    if not addr:
        return {
            "building_no": "",
            "street": "",
            "secondary_no": "",
            "district": "",
            "city": "",
            "postal_code": "",
            "country": "",
        }
    return {
        "building_no": addr.get("building_no") or "",
        "street": addr.address_line1 or "",
        "secondary_no": addr.get("secondary_no") or "",
        "district": addr.get("district") or "",
        "city": addr.city or "",
        "postal_code": addr.pincode or "",
        "country": addr.country or "",
    }


def _save_address(addr, data):
    """Apply form data to an Address doc."""
    addr.building_no = data.get("building_no") or ""
    addr.address_line1 = data.get("street") or ""
    addr.secondary_no = data.get("secondary_no") or ""
    addr.district = data.get("district") or ""
    addr.city = data.get("city") or ""
    addr.pincode = data.get("postal_code") or ""
    addr.country = data.get("country") or None
    addr.flags.ignore_permissions = True
    addr.save()
    return addr


def _create_address(doctype, name, data, title):
    """Create a new Address doc linked to the given doctype/name."""
    addr = frappe.get_doc({
        "doctype": "Address",
        "address_title": title or name,
        "address_type": "Billing",
        "address_line1": data.get("street") or "-",
        "city": data.get("city") or "-",
        "country": data.get("country") or None,
        "pincode": data.get("postal_code") or "",
        "building_no": data.get("building_no") or "",
        "secondary_no": data.get("secondary_no") or "",
        "district": data.get("district") or "",
        "is_primary_address": 1,
        "links": [{"link_doctype": doctype, "link_name": name}],
    })
    addr.flags.ignore_permissions = True
    addr.insert()
    return addr


@frappe.whitelist()
def get_establishment():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    doctype, name = _get_linked_doc(frappe.session.user)

    if not name:
        return {"entity_type": None}

    if doctype == "Lead":
        lead = frappe.get_doc("Lead", name)
        addr = _get_linked_address("Lead", name)
        address_data = _address_to_dict(addr)
        if not addr:
            address_data["city"] = lead.city or ""
            address_data["country"] = lead.country or ""
        return {
            "entity_type": "Lead",
            "entity_name": name,
            "organization_name": lead.company_name or "",
            "industry": lead.industry or "",
            "market_segment": lead.market_segment or "",
            "territory": lead.territory or "",
            "website": lead.website or "",
            **address_data,
        }

    customer = frappe.get_doc("Customer", name)
    addr = None
    if customer.customer_primary_address:
        addr = frappe.get_doc("Address", customer.customer_primary_address)
    else:
        addr = _get_linked_address("Customer", name)
    return {
        "entity_type": "Customer",
        "entity_name": name,
        "organization_name": customer.customer_name or "",
        "customer_type": customer.customer_type or "",
        "customer_group": customer.customer_group or "",
        "industry": customer.industry or "",
        "market_segment": customer.market_segment or "",
        "territory": customer.territory or "",
        "website": customer.website or "",
        **_address_to_dict(addr),
    }


@frappe.whitelist()
def update_establishment(data):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if isinstance(data, str):
        import json
        data = json.loads(data)

    doctype, name = _get_linked_doc(frappe.session.user)
    if not name:
        frappe.throw(_("No linked Lead or Customer found"))

    if doctype == "Lead":
        lead = frappe.get_doc("Lead", name)
        lead.company_name = data.get("organization_name", lead.company_name)
        lead.industry = data.get("industry") or None
        lead.market_segment = data.get("market_segment") or None
        lead.territory = data.get("territory") or None
        lead.website = data.get("website", lead.website)
        lead.city = data.get("city", lead.city)
        lead.country = data.get("country") or None
        lead.flags.ignore_permissions = True
        lead.save()

        addr = _get_linked_address("Lead", name)
        if addr:
            _save_address(addr, data)
        else:
            _create_address("Lead", name, data, lead.company_name or lead.lead_name)
    else:
        customer = frappe.get_doc("Customer", name)
        customer.customer_name = data.get("organization_name", customer.customer_name)
        customer.customer_type = data.get("customer_type", customer.customer_type)
        customer.customer_group = data.get("customer_group") or None
        customer.industry = data.get("industry") or None
        customer.market_segment = data.get("market_segment") or None
        customer.territory = data.get("territory") or None
        customer.website = data.get("website", customer.website)
        customer.flags.ignore_permissions = True
        customer.save()

        if customer.customer_primary_address:
            addr = frappe.get_doc("Address", customer.customer_primary_address)
            _save_address(addr, data)
        else:
            addr = _get_linked_address("Customer", name)
            if addr:
                _save_address(addr, data)
            else:
                addr = _create_address("Customer", name, data, customer.customer_name)
                customer.customer_primary_address = addr.name
                customer.flags.ignore_permissions = True
                customer.save()

    frappe.db.commit()
    return {"success": True, "message": _("Establishment updated successfully")}
