import frappe
from frappe import _


def validate(doc, method):
    validate_facility_address(doc)
    enforce_facility_address_source(doc)


def enforce_facility_address_source(doc):
    """The Facility is the single source of truth for its linked Address.

    On every save of a Facility-linked Address, re-pull the Facility-owned fields
    from the Facility so any direct edit to them is reverted (one-way ownership).
    Non-owned fields (address_title, address_type, email, phone, ...) stay editable.
    """
    from naqel.nq_crm.doctype.facility.facility import FACILITY_ADDRESS_FIELD_MAP

    facility_link = next(
        (link for link in doc.links if link.link_doctype == "Facility"), None
    )
    if not facility_link:
        return

    facility = frappe.db.get_value(
        "Facility",
        facility_link.link_name,
        list(FACILITY_ADDRESS_FIELD_MAP.values()),
        as_dict=True,
    )
    if not facility:
        return

    for address_field, facility_field in FACILITY_ADDRESS_FIELD_MAP.items():
        doc.set(address_field, facility.get(facility_field))


def validate_facility_address(doc):
    facility_links = [link for link in doc.links if link.link_doctype == "Facility"]
    if not facility_links:
        return

    allow_different_for_sub = frappe.db.get_single_value(
        "Address Settings", "allow_different_address_for_sub_facility"
    )

    for link in facility_links:
        facility_name = link.link_name
        facility = frappe.db.get_value("Facility", facility_name, ["parent_facility"], as_dict=True)
        if not facility:
            continue

        if facility.parent_facility:
            if not allow_different_for_sub:
                frappe.throw(
                    _(
                        "Facility {0} is a sub-facility of {1} and cannot have its own address. "
                        "It inherits the address from its parent facility. "
                        "To allow this, enable <b>Allow Different Address For Sub-Facility</b> "
                        "in Address Settings."
                    ).format(frappe.bold(facility_name), frappe.bold(facility.parent_facility))
                )

        # One-address rule: each facility can only be linked to one address
        existing = frappe.db.get_all(
            "Dynamic Link",
            filters={
                "parenttype": "Address",
                "link_doctype": "Facility",
                "link_name": facility_name,
                "parent": ("!=", doc.name),
            },
            pluck="parent",
            limit=1,
        )
        if existing:
            frappe.throw(
                _(
                    "Facility {0} is already linked to address {1}. "
                    "A facility can only have one address."
                ).format(frappe.bold(facility_name), frappe.bold(existing[0]))
            )
