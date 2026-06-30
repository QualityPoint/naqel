import frappe
from frappe import _
from frappe.model.document import Document


class ContainerFillLevel(Document):
    def validate(self):
        self.validate_default_fill_level()

    def validate_default_fill_level(self):
        if not self.is_default and not self._get_previous_default():
            self.is_default = 1
            if frappe.is_setup_complete():
                frappe.msgprint(
                    _("Setting this Container Fill Level as default as there is no other default"))

        if self.is_default and self.disabled:
            frappe.throw(_("Default Container Fill Level cannot be disabled"))

    def on_update(self):
        if self.is_default and (previous_default := self._get_previous_default()):
            frappe.db.set_value("Container Fill Level",
                                previous_default, "is_default", 0)

    def on_trash(self):
        if self.is_default:
            frappe.throw(
                _("Default Container Fill Level cannot be deleted"))

    def _get_previous_default(self) -> str | None:
        return frappe.db.get_value("Container Fill Level", {"is_default": 1, "name": ("!=", self.name)})
