import frappe
from frappe import _

ALLOWED_DOCTYPES = {
    "Industry Type",
    "Market Segment",
    "Territory",
    "Customer Group",
    "Country",
    "Gender",
    "ISIC Classification",
    "Address Division",
    "Identification Number",
    "License",
}


@frappe.whitelist()
def search(doctype, txt="", page_length=20, filters=None, lang=None):
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"))

    if doctype not in ALLOWED_DOCTYPES:
        frappe.throw(_("Not allowed"))

    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    if lang:
        frappe.local.lang = lang

    txt = (txt or "").strip()
    meta = frappe.get_meta(doctype)
    search_field = meta.title_field or "name"

    query_filters = filters or {}

    results = frappe.get_list(
        doctype,
        filters=query_filters,
        fields=["name", search_field],
        order_by=search_field,
        page_length=0,
        ignore_permissions=True,
    )

    country_translations = {}
    if doctype == "Country":
        from frappe.geo.country_info import get_translated_countries
        country_translations = get_translated_countries()

    options = []
    for r in results:
        value = r.name
        raw = r.get(search_field, value)
        label = country_translations.get(raw, _(raw)) if country_translations else _(raw)
        options.append({"value": value, "label": label})

    if txt:
        txt_lower = txt.lower()
        options = [o for o in options if txt_lower in o["label"].lower() or txt_lower in o["value"].lower()]

    options.sort(key=lambda o: o["label"])

    return options[:int(page_length)]
