# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe


def get_contract_status(is_signed, is_milestone_based, start_date, end_date):
    """
    Pure function — derives Service Contract status from document fields.

    Duration-Based (is_milestone_based=False):
        not signed          → Unsigned
        signed, within dates → Active
        signed, past end    → Inactive

    Milestone-Based (is_milestone_based=True):
        not signed → Unsigned
        signed     → Active  (Completed/Terminated are set manually via buttons)
    """
    if not is_signed:
        return "Unsigned"

    if not is_milestone_based:
        from frappe.utils import getdate, nowdate
        today = getdate(nowdate())
        start = getdate(start_date) if start_date else today
        end = getdate(end_date) if end_date else None

        if end and today > end:
            return "Inactive"
        if today >= start:
            return "Active"
        # Signed but start_date is in the future — the contract is valid,
        # it simply hasn't started yet.  "Unsigned" would be misleading
        # because the document IS signed.
        return "Active"

    # Milestone-Based — only auto transition is Unsigned → Active on signing
    return "Active"


def update_status_for_contracts():
    """
    Daily scheduler task — recalculates Active/Inactive for all submitted,
    signed, Duration-Based Service Contracts whose status is not manually locked.
    """
    MANUAL_STATUSES = {"On Hold", "Terminated", "Cancelled"}

    contracts = frappe.get_all(
        "Service Contract",
        filters={
            "docstatus": 1,
            "is_signed": 1,
            "is_milestone_based": 0,
            "status": ("not in", list(MANUAL_STATUSES)),
        },
        fields=["name", "start_date", "end_date"],
    )

    for contract in contracts:
        new_status = get_contract_status(
            is_signed=True,
            is_milestone_based=False,
            start_date=contract.start_date,
            end_date=contract.end_date,
        )
        frappe.db.set_value("Service Contract", contract.name,
                            "status", new_status, update_modified=False)

    frappe.db.commit()
