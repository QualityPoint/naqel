import frappe
from frappe import _
import json


def make_fixtures_from_json(doctype, json_filename, unique_field):
    """
    Generic function to create fixtures from JSON data file

    Args:
        doctype: The DocType name (e.g., "Waste Type")
        json_filename: JSON file name in data/ directory (e.g., "waste_type_data.json")
        unique_field: Field name to check for existence (e.g., "waste_name")
    """
    records = json.loads(
        open(frappe.get_app_path("naqel", "data", json_filename)).read()
    )

    for record in records:
        unique_value = record.get(unique_field)
        if not frappe.db.exists(doctype, _(unique_value)):
            try:
                doc = frappe.get_doc({
                    "doctype": doctype,
                    **record
                })
                doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
                frappe.db.commit()
                print(f"Created {doctype}: {unique_value}")
            except Exception as e:
                error_msg = str(e)[:100]
                frappe.log_error(error_msg, f"{doctype}: {unique_value}")
                print(
                    f"Error creating {doctype}: {unique_value} - {error_msg}")
