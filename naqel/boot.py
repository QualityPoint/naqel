# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint


def boot_session(bootinfo):
    """Expose lightweight settings to every desk client via frappe.boot.

    Mirrors erpnext's pattern of surfacing Quotation validity days through
    sysdefaults so the client can default fields without a per-user permission
    check on the (System Manager-only) Service Settings single doctype.
    """
    bootinfo.sysdefaults.service_quotation_valid_till = cint(
        frappe.db.get_single_value("Service Settings", "default_valid_till")
    )
