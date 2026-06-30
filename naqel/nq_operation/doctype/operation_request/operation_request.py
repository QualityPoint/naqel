# Copyright (c) 2026, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OperationRequest(Document):
	def validate(self):
		self.validate_container()

	def validate_container(self):
		if not self.container:
			return
		container = frappe.db.get_value(
			"Container", self.container, ["company", "container_type"], as_dict=True
		)
		if not container:
			frappe.throw(_("The selected container does not exist."))
		if container.company != self.company:
			frappe.throw(_("The selected container does not belong to the selected company."))
		if container.container_type != self.container_type:
			frappe.throw(_("The selected container does not match the selected container type."))
