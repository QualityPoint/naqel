# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today
from frappe.utils.user import is_website_user

SURVEY_TYPE_ORDER_TYPE = {
    "Fill Level": "Waste Collection",
    "Issue": "Inspection",
    "Cleaning and Disinfection": "Cleaning and Disinfection",
}


class ContainerSurvey(Document):
    def validate(self):
        self.resolve_portal_user()
        self.validate_evidence()
        self.validate_fill_level()

    def on_submit(self):
        self.update_container_fill_level()
        self.mark_schedule_completed()

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def resolve_portal_user(self):
        if not is_website_user():
            return
        self.via_customer_portal = 1

    def validate_evidence(self):
        if not self.image:
            frappe.throw(_("Photo evidence is required."))
        if self.survey_type in ("Issue", "Cleaning and Disinfection") and not self.description:
            frappe.throw(
                _("Description is required for {0} surveys.").format(self.survey_type))

    def validate_fill_level(self):
        if self.survey_type != "Fill Level":
            return
        if self.fill_level:
            fl = frappe.db.get_value("Container Fill Level", self.fill_level, [
                "fill_level_action", "disabled"], as_dict=True)
            if fl.disabled:
                frappe.throw(
                    _("Selected fill level is disabled."))
            if fl.fill_level_action == "Ignore":
                frappe.throw(
                    _("Cannot select fill level with marked action 'Ignore'."))

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def update_container_fill_level(self):
        if self.survey_type != "Fill Level":
            return
        frappe.db.set_value("Container", self.container,
                            "fill_level", self.fill_level)

    def mark_schedule_completed(self):
        if not self.schedule_reference:
            return
        schedule = frappe.get_doc(
            "Container Operation Schedule", self.schedule_reference)
        for row in schedule.scheduled_dates:
            if row.completion_status == "Pending" and not row.reference_document:
                row.completion_status = "Completed"
                row.completed_on = today()
                row.reference_doctype = "Container Survey"
                row.reference_document = self.name
                break
        schedule.save(ignore_permissions=True)


def has_website_permission(doc, ptype, user, verbose=False):
    return doc.surveyed_by == user
