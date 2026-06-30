# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from naqel.utils.uom import validate_uom_field


class NaqelSettings(Document):
	def validate(self):
		# Validate all UOM fields
		validate_uom_field(self, "default_volume_unit", "Volume")
		validate_uom_field(self, "default_mass_unit", "Mass")
		validate_uom_field(self, "default_length_unit", "Length")
		validate_uom_field(self, "default_density_unit", "Density")
		validate_uom_field(self, "default_area_unit", "Area")
