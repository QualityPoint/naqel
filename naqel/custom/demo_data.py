import frappe
from frappe import _
import json


def make_demo_fixtures(doctype, json_filename, unique_field):
    """
    Create demo fixtures from JSON data file

    Args:
            doctype: The DocType name (e.g., "Container Type")
            json_filename: JSON file name in data/demo/ directory (e.g., "container_type_data.json")
            unique_field: Field name to check for existence (e.g., "container_type")
    """
    records = json.loads(
        open(frappe.get_app_path("naqel", "data", "demo", json_filename)).read()
    )

    created_count = 0
    for record in records:
        unique_value = record.get(unique_field)
        if not frappe.db.exists(doctype, _(unique_value)):
            try:
                doc = frappe.get_doc({
                    "doctype": doctype,
                    **record
                })
                doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
                created_count += 1
            except Exception as e:
                error_msg = str(e)[:100]
                frappe.log_error(
                    error_msg, f"Demo Data - {doctype}: {unique_value}")
                frappe.msgprint(_("Error creating {0}: {1}").format(
                    unique_value, error_msg), indicator="red")

    if created_count > 0:
        frappe.db.commit()
        frappe.msgprint(_("Created {0} {1} records").format(
            created_count, doctype), indicator="green")
    else:
        frappe.msgprint(_("All {0} records already exist").format(
            doctype), indicator="blue")


def clear_demo_fixtures(doctype):
    """
    Clear all demo fixtures for a specific doctype

    Args:
            doctype: The DocType name (e.g., "Container Type")
    """
    try:
        # Handle special cleanup for doctypes with dependencies
        if doctype == "Waste Removal Mechanism":
            # First, clear all removal mechanism references from Container Types
            container_types = frappe.get_all("Container Type", pluck="name")
            for container_name in container_types:
                container_doc = frappe.get_doc(
                    "Container Type", container_name)
                if container_doc.removal_mechanisms:
                    container_doc.removal_mechanisms = []
                    container_doc.save(ignore_permissions=True)
            if container_types:
                frappe.db.commit()
                frappe.msgprint(
                    _("Cleared removal mechanism references from {0} Container Types").format(
                        len(container_types)),
                    indicator="blue"
                )

        records = frappe.get_all(doctype, pluck="name")
        deleted_count = len(records)

        if deleted_count == 0:
            frappe.msgprint(_("No {0} records to delete").format(
                doctype), indicator="blue")
            return

        for name in records:
            frappe.delete_doc(
                doctype, name, ignore_permissions=True, force=True)

        frappe.db.commit()
        frappe.msgprint(_("Deleted {0} {1} records").format(
            deleted_count, doctype), indicator="green")
    except Exception as e:
        error_msg = str(e)[:100]
        frappe.log_error(error_msg, f"Clear Demo Data - {doctype}")
        frappe.throw(_("Error clearing {0}: {1}").format(doctype, error_msg))


@frappe.whitelist()
def generate_all_demo_data():
    """Generate demo data for all configured doctypes"""
    # Order matters - dependencies first
    demo_data_config = [
        ("Facility UOM", "facility_uom_data.json", "uom_name"),
        ("Waste Removal Mechanism",
         "waste_removal_mechanism_data.json", "removal_mechanism_name"),
        ("Container Type", "container_type_data.json", "container_type"),
        ("Service Configuration", "service_configuration_data.json", "name"),
    ]

    for doctype, json_file, unique_field in demo_data_config:
        make_demo_fixtures(doctype, json_file, unique_field)


@frappe.whitelist()
def clear_demo_data(doctypes=None):
    """
    Clear demo data for selected doctypes

    Args:
            doctypes: JSON string of doctype names list (e.g., '["Container Type", "Waste Removal Mechanism"]')
    """
    if doctypes:
        if isinstance(doctypes, str):
            doctypes = json.loads(doctypes)
    else:
        doctypes = []

    if not doctypes:
        frappe.throw(_("Please select at least one doctype to clear"))

    # Clear in reverse order to handle dependencies (dependents first)
    clear_order = ["Service Configuration", "Container Type",
                   "Waste Removal Mechanism", "Facility UOM"]

    for doctype in clear_order:
        if doctype in doctypes:
            clear_demo_fixtures(doctype)
