# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceTermsandConditions(Document):
    def validate(self):
        self.validate_default_terms_and_conditions()

    def validate_default_terms_and_conditions(self):
        if not self.is_default and not self._get_previous_default():
            self.is_default = 1
            if frappe.is_setup_complete():
                frappe.msgprint(
                    _("Setting this Service Terms and Conditions as default as there is no other default"))

        if self.is_default and self.disabled:
            frappe.throw(
                _("Default Service Terms and Conditions cannot be disabled"))

    def on_update(self):
        if self.is_default and (previous_default := self._get_previous_default()):
            frappe.db.set_value("Service Terms and Conditions",
                                previous_default, "is_default", 0)

    def on_trash(self):
        if self.is_default:
            frappe.throw(
                _("Default Service Terms and Conditions cannot be deleted"))

    def _get_previous_default(self) -> str | None:
        return frappe.db.get_value("Service Terms and Conditions", {"is_default": 1, "name": ("!=", self.name)})


@frappe.whitelist()
def get_terms_and_conditions(template_name, doc):
    if isinstance(doc, str):
        doc = json.loads(doc)

    terms_and_conditions = frappe.get_doc(
        "Service Terms and Conditions", template_name)

    if terms_and_conditions.terms:
        return frappe.render_template(terms_and_conditions.terms, doc)
