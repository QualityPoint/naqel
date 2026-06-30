import frappe
from frappe import _
from erpnext.projects.doctype.project.project import Project


class NaqelProject(Project):
    def validate(self):
        super().validate()
        self.validate_service_contract()

    def validate_service_contract(self):
        if not self.get("service_contract"):
            return

        sc = frappe.db.get_value(
            "Service Contract",
            self.service_contract,
            ["company", "customer"],
            as_dict=True,
        )

        if not sc:
            frappe.throw(_("Service Contract {0} does not exist.").format(
                self.service_contract))

        if sc.company != self.company:
            frappe.throw(
                _("Service Contract {0} belongs to company {1}, but this project is under {2}.").format(
                    self.service_contract, sc.company, self.company
                )
            )

        if self.get("customer") and sc.customer != self.customer:
            frappe.throw(
                _("Service Contract {0} belongs to customer {1}, but this project is for {2}.").format(
                    self.service_contract, sc.customer, self.customer
                )
            )
