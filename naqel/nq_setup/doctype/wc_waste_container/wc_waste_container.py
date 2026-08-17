# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WCWasteContainer(Document):
	
	def db_insert(self, *args, **kwargs):
		raise NotImplementedError

	def load_from_db(self, *args, **kwargs):
		raise NotImplementedError

	def db_update(self, *args, **kwargs):
		raise NotImplementedError

	def delete(self, *args, **kwargs):
		raise NotImplementedError

