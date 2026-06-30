# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe


def update_service_quotation_status(doc, method=None):
    """When a Sales Order is submitted or cancelled, recompute the status of any Service
    Quotation its items were raised from — the Naqel equivalent of ERPNext's
    Sales Order.update_prevdoc_status (flips the quotation in/out of 'Sales Order')."""
    quotations = {row.service_quotation for row in doc.items if row.get("service_quotation")}
    for name in quotations:
        frappe.get_doc("Service Quotation", name).set_sales_order_status()
