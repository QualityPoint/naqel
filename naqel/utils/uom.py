import frappe
from frappe import _


@frappe.whitelist()
def validate_uom_field(doc, field, category):
    uom_value = doc.get(field)

    if not uom_value:
        return

    valid_uoms = frappe.db.get_all(
        "UOM", filters={"category": category}, pluck="name")

    if uom_value not in valid_uoms:
        frappe.throw(
            _("The selected UOM '{0}' in field '{1}' is not defined under category '{2}'").format(
                uom_value, doc.meta.get_label(field), _(category)
            )
        )
