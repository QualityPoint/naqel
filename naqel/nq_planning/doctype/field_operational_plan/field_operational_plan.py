# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FieldOperationalPlan(Document):
    def validate(self):
        self.validate_customer_project()

    def validate_customer_project(self):
        if self.project:
            proj = frappe.db.get_value(
                "Project", self.project, ["customer", "company"], as_dict=True)
            if proj:
                if proj.customer != self.customer:
                    frappe.throw(
                        _("The selected project does not belong to the selected customer."))
                if proj.company != self.company:
                    frappe.throw(
                        _("The selected project does not belong to the selected company."))
            else:
                frappe.throw(_("The selected project does not exist."))
