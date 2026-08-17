# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ContainerPrice(Document):
	def validate(self):
		self.validate_default_per_service_type()
		self.validate_unique_configuration()
		self.validate_positive_values()

	def validate_default_per_service_type(self):
		if not self.is_default and not self._get_previous_default():
			self.is_default = 1
			if frappe.is_setup_complete():
				frappe.msgprint(
					_("Setting this Container Price as default as there is no other default for {0} under {1}.").format(
						frappe.bold(self.container_type), frappe.bold(self.service_type)
					))

	def validate_unique_configuration(self):
		duplicate = frappe.db.get_value("Container Price", {
			"container_type": self.container_type,
			"service_type": self.service_type,
			"collection_count": self.collection_count,
			"collection_period_count": self.collection_period_count,
			"collection_period_uom": self.collection_period_uom,
			"name": ("!=", self.name)
		})
		if duplicate:
			frappe.throw(
				_("A Container Price with the same collection configuration already exists for {0} under {1}.").format(
					frappe.bold(self.container_type), frappe.bold(self.service_type)
				))

	def validate_positive_values(self):
		if not self.container_rate or self.container_rate <= 0:
			frappe.throw(_("Rate must be greater than 0."))
		if not self.collection_count or self.collection_count < 1:
			frappe.throw(_("Collection Count must be at least 1."))
		if not self.collection_period_count or self.collection_period_count < 1:
			frappe.throw(_("Collection Period Count must be at least 1."))

	def on_update(self):
		if self.is_default and (previous_default := self._get_previous_default()):
			frappe.db.set_value("Container Price", previous_default, "is_default", 0)

	def on_trash(self):
		if self.is_default:
			frappe.throw(_("Default Container Price cannot be deleted."))

	def _get_previous_default(self) -> str | None:
		return frappe.db.get_value("Container Price", {
			"is_default": 1,
			"container_type": self.container_type,
			"service_type": self.service_type,
			"name": ("!=", self.name)
		})
