import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def custom_fields():
    """Naqel specific custom fields that need to be added to the system."""
    return {
        "Address": [
            {
                "fieldname": "building_no",
                "label": _("Building No."),
                "fieldtype": "Data",
                "insert_after": "address_type",
            },
            {
                "fieldname": "secondary_no",
                "label": _("Secondary No."),
                "fieldtype": "Data",
                "insert_after": "address_line2",
            },
            {
                "fieldname": "district",
                "label": _("District"),
                "fieldtype": "Data",
                "insert_after": "secondary_no",
            }
        ],
        "Company": [
            {
                "fieldname": "credentials_tab",
                "label": _("Credentials"),
                "fieldtype": "Tab Break",
                "insert_after": "old_parent",
            },
            {
                "fieldname": "credentials_section",
                "fieldtype": "Section Break",
                "insert_after": "credentials_tab",
            },
            {
                "fieldname": "credentials",
                "label": _("Credentials"),
                "fieldtype": "Table",
                "options": "Company Credential",
                "insert_after": "credentials_section",
            }
        ],
        "Project": [
            {
                "fieldname": "service_contract",
                "label": _("Service Contract"),
                "fieldtype": "Link",
                "options": "Service Contract",
                "insert_after": "customer",
            }
        ],
        "Sales Order Item": [
            {
                "fieldname": "service_quotation",
                "label": _("Service Quotation"),
                "fieldtype": "Link",
                "options": "Service Quotation",
                "is_system_generated": 1,
                "print_hide": 1,
                "no_copy": 1,
                "read_only": 1,
                "insert_after": "prevdoc_docname",
            },
            {
                "fieldname": "service_quotation_item",
                "label": _("Service Quotation Item"),
                "fieldtype": "Link",
                "options": "Service Quotation Item",
                "is_system_generated": 1,
                "print_hide": 1,
                "no_copy": 1,
                "read_only": 1,
                "insert_after": "service_quotation",
            },
        ]
    }


def make_custom_fields():
    """Create Naqel specific custom fields"""
    create_custom_fields(custom_fields(), ignore_validate=True)


def delete_custom_fields():
    """
    :param custom_fields: a dict like `{'Company': [{fieldname: 'crn', ...}]}`
    """
    for doctype, fields in custom_fields().items():
        frappe.db.delete(
            "Custom Field",
            {
                "fieldname": ("in", [field["fieldname"] for field in fields]),
                "dt": doctype,
            },
        )

        frappe.clear_cache(doctype=doctype)
