# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def format_currency_in_words(amount, currency):
    """Convert a numeric amount to its written representation in the active locale."""
    from frappe.utils.data import in_words
    from decimal import Decimal

    currency_doc = frappe.db.get_value(
        "Currency", currency, ["currency_name", "fraction"], as_dict=True, cache=True
    ) or frappe._dict(currency_name=currency, fraction="")

    currency_name = currency_doc.currency_name or currency
    fraction_name = currency_doc.fraction or ""

    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    integer_part, fractional_part = str(amount).split('.')

    # in_words respects frappe.local.lang so returns Arabic when locale is Arabic
    integer_words = in_words(int(integer_part)).title()

    if int(fractional_part) > 0:
        fractional_words = in_words(int(fractional_part)).title()
        return (
            f"{integer_words} {_(currency_name, context='Currency')} "
            f"{_('and')} {fractional_words} {_(fraction_name, context='Currency')} {_('only.')}"
        )

    return f"{integer_words} {_(currency_name, context='Currency')} {_('only.')}"


@frappe.whitelist()
def get_default_terms_template():
    """Get the default Service Contract Terms Template."""
    return frappe.db.get_value(
        "Service Contract Terms Template",
        {"is_default": 1},
        "name",
    )


@frappe.whitelist()
def get_terms_template(template_name):
    """
    Fetch the raw terms and conditions from the Service Contract Terms Template.

    The Jinja is intentionally NOT rendered. The term fields are Code (Jinja) fields
    that hold the raw template source verbatim (like a Print Format's html field);
    it is rendered for display only at print time, by the Print Format.
    """
    if not template_name:
        return

    try:
        template_doc = frappe.get_doc("Service Contract Terms Template", template_name)
    except frappe.DoesNotExistError:
        frappe.throw(
            _("Service Contract Terms Template {0} does not exist").format(template_name))

    return [
        {
            "title_primary": terms.title_primary,
            "terms_and_conditions_primary": terms.terms_and_conditions_primary or "",
            "title_foreign": terms.title_foreign,
            "terms_and_conditions_foreign": terms.terms_and_conditions_foreign or "",
        }
        for terms in template_doc.get("terms", [])
    ]


@frappe.whitelist()
def get_renewal_settings():
    """Return Contract Settings renewal fields for client-side grace period calculation."""
    return {
        "renewal_grace_period": frappe.db.get_single_value("Contract Settings", "renewal_grace_period") or 1,
        "grace_period_uom": frappe.db.get_single_value("Contract Settings", "grace_period_uom") or "Month",
    }
