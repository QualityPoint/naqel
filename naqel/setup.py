import frappe

from naqel.custom.custom_fields import delete_custom_fields, make_custom_fields
from naqel.custom.fixtures import make_fixtures
from naqel.custom.property_setter import create_property_setter, remove_property_setter


def after_install():
    create_property_setter()
    make_custom_fields()
    make_fixtures()
    set_single_defaults()
    add_parties_to_session_defaults()


def before_uninstall():
    # remove_property_setter()
    delete_custom_fields()


def set_single_defaults():
    """Set default values for single DocTypes"""
    # Set defaults for Naqel Settings
    try:
        doc = frappe.get_doc("Naqel Settings")

        # Default UOM values
        defaults = {
            "default_volume_unit": "Cubic Meter",
            "default_mass_unit": "Kg",
            "default_density_unit": "Kilogram/Cubic Meter",
            "default_area_unit": "Square Meter",
            "default_length_unit": "Meter",
            # Global Defaults
            "default_currency": "SAR",
            "hide_currency_symbol": "No",
            "disable_in_words": 0,
        }

        # Only set if not already set
        for field, value in defaults.items():
            if not doc.get(field):
                doc.set(field, value)

        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)

        # Enable default currency (SAR) if it's not already enabled
        if doc.default_currency:
            currency_enabled = frappe.db.get_value(
                "Currency", doc.default_currency, "enabled")
            if not currency_enabled:
                frappe.db.set_value(
                    "Currency", doc.default_currency, "enabled", 1)

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e)[:100], "Naqel Settings Setup")


def add_parties_to_session_defaults():
    """Register Producer and Transporter in Session Default Settings.

    This mirrors how ERPNext registers Company so that:
    - `frappe.defaults.get_user_default("producer")` works after login.
    - `frappe.defaults.get_user_default("transporter")` works after login.
    - Defaults are cleared automatically on logout via the on_logout hook.
    """
    try:
        settings = frappe.get_single("Session Default Settings")
        existing = {row.ref_doctype for row in settings.session_defaults}

        changed = False
        for doctype in ("Producer", "Transporter"):
            if doctype not in existing:
                settings.append("session_defaults", {"ref_doctype": doctype})
                changed = True

        if changed:
            settings.save(ignore_permissions=True)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e)[:200], "Naqel Session Defaults Setup")
