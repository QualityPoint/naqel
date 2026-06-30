# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def calculate_duration(start_date, end_date, duration_uom):
    """
    Calculate duration between two dates (inclusive of both start and end dates).
    Strategy: add 1 day to end_date (exclusive end) so that full-month/year
    ranges resolve to exact whole numbers via relativedelta.
    e.g. Jan 1 → Jan 31 (+1 day → Feb 1) = exactly 1 month.
    """
    import calendar
    from dateutil.relativedelta import relativedelta
    from frappe.utils import getdate, add_days, flt

    if not (start_date and end_date and duration_uom):
        return None

    start = getdate(start_date)
    end = getdate(end_date)

    if end < start:
        frappe.throw(_("End Date cannot be before Start Date"))

    exclusive_end = add_days(end, 1)

    if duration_uom == "Day":
        return flt((exclusive_end - start).days, 2)

    elif duration_uom == "Month":
        rd = relativedelta(exclusive_end, start)
        total_months = rd.years * 12 + rd.months
        if rd.days == 0:
            return flt(total_months, 2)
        partial_start = start + relativedelta(months=total_months)
        days_in_partial = calendar.monthrange(
            partial_start.year, partial_start.month)[1]
        return flt(total_months + rd.days / days_in_partial, 2)

    elif duration_uom == "Year":
        rd = relativedelta(exclusive_end, start)
        if rd.months == 0 and rd.days == 0:
            return flt(rd.years, 2)
        return flt(rd.years + rd.months / 12 + rd.days / 365.25, 2)

    return None
