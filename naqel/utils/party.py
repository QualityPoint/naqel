import frappe
from frappe import _
from frappe.utils import flt


def set_conversion_factor(doc):
    """Set conversion_factor on a document with service_configuration and facility_uom fields."""
    if not doc.service_configuration or not doc.facility_uom:
        doc.conversion_factor = 1
        return

    config_doctype = doc.get("calculation_based_on") or "Service Configuration"
    config_name = doc.service_configuration

    if config_doctype == "Regional Service Configuration":
        config_name = frappe.db.get_value(
            "Regional Service Configuration", config_name, "service_configuration"
        )
        if not config_name:
            doc.conversion_factor = 1
            return

    default_uom = frappe.db.get_value("Service Configuration", config_name, "facility_uom")

    if doc.facility_uom == default_uom:
        doc.conversion_factor = 1
        return

    factor = frappe.db.get_value(
        "Facility UOM Conversion",
        {"parent": config_name, "subsidiary_uom": doc.facility_uom},
        "conversion_factor",
    )
    doc.conversion_factor = flt(factor) or 1


def set_net_facility_measurement(doc):
    """Set net_facility_measurement = facility_measurement × conversion_factor."""
    doc.net_facility_measurement = flt(doc.facility_measurement) * flt(doc.conversion_factor or 1)


def validate_facility_belongs_to_party(doc, party_type_field, party_field):
    """Validate that the facility is linked to the party via Dynamic Link."""
    party_type = doc.get(party_type_field)
    party = doc.get(party_field)

    if not doc.facility or not party_type or not party:
        return

    linked = frappe.db.exists(
        "Dynamic Link",
        {
            "parenttype": "Facility",
            "parent": doc.facility,
            "link_doctype": party_type,
            "link_name": party,
        },
    )
    if not linked:
        frappe.throw(
            _("Facility {0} does not belong to {1} {2}.").format(
                frappe.bold(doc.facility),
                _(party_type),
                frappe.bold(party),
            )
        )


def clear_milestone_fields(doc, duration_field="service_duration", clear_when_milestone=True):
    """Clear end_date, duration_uom, and the duration field based on is_milestone_based.

    Args:
        clear_when_milestone: If True (Service Request/Contract), clear when IS milestone-based.
            If False (Service Quotation), clear when NOT milestone-based.
    """
    should_clear = doc.is_milestone_based if clear_when_milestone else not doc.is_milestone_based
    if should_clear:
        doc.end_date = None
        doc.set(duration_field, None)
        doc.duration_uom = None


def validate_duration_fields(doc, required_when_not_milestone=True):
    """Validate end_date, duration_uom, and date ordering.

    Args:
        required_when_not_milestone: If True (Service Request/Contract), require fields
            when NOT milestone-based. If False (Service Quotation), require when IS milestone-based.
    """
    should_validate = (not doc.is_milestone_based) if required_when_not_milestone else doc.is_milestone_based
    if not should_validate:
        return

    label = _("milestone-based") if not required_when_not_milestone else _("not milestone-based")
    if not doc.end_date:
        frappe.throw(_("End Date is required when service is {0}.").format(label))
    if not doc.duration_uom:
        frappe.throw(_("Duration UOM is required when service is {0}.").format(label))
    if doc.end_date and doc.start_date and doc.end_date < doc.start_date:
        frappe.throw(_("End Date cannot be before Start Date."))


def set_customer_name(doc, party_type_field, party_field):
    """Set customer_name from the linked Customer or Lead."""
    party_type = doc.get(party_type_field)
    party = doc.get(party_field)

    if not party:
        doc.customer_name = ""
    elif party_type == "Customer":
        doc.customer_name = frappe.db.get_value("Customer", party, "customer_name") or ""
    elif party_type == "Lead":
        lead_name, company_name = frappe.db.get_value(
            "Lead", party, ["lead_name", "company_name"]
        ) or ("", "")
        doc.customer_name = company_name or lead_name
