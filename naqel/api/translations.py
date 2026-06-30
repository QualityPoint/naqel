import frappe


@frappe.whitelist(allow_guest=True)
def get_translations(lang: str = "ar") -> dict:
    """Return the full translation dictionary for *lang*.

    Called by the Vue SPA at startup so it can translate UI strings using
    the same source of truth as the Frappe backend (ar.csv etc.).
    Results are cached in Redis by frappe.translate, so this is cheap.
    """
    if lang not in ("ar", "en"):
        frappe.throw(frappe._("Unsupported language: {0}").format(
            lang), frappe.ValidationError)

    # English is the source language — no translation needed.
    if lang == "en":
        return {}

    return frappe.translate.get_all_translations(lang)
