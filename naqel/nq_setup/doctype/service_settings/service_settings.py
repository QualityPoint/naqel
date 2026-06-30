# Copyright (c) 2026, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from naqel.utils.pricing import PRIORITY_VALUES, SCOPE_TYPES, validate_scope_rows


class ServiceSettings(Document):
	def validate(self):
		self.validate_pricing_rule_priority()

	def validate_pricing_rule_priority(self):
		"""Enforce the Service Pricing Rule Priority table integrity.

		Frappe cannot enforce this declaratively (``unique`` is invalid on a Select
		and meaningless on a child-table field), so it is enforced here.

		The table is either empty (resolution falls back to code defaults) or fully
		specified: exactly one row per dimension, with priority ranks {1, 2, 3} each
		used once. Partial configurations are rejected because they would leave a
		dimension's weight undefined.
		"""
		rows = self.get("pricing_rule_priority") or []

		# Empty table is allowed (falls back to default dimension weighting).
		if not rows:
			return

		# Shared check: valid scope_type values, no duplicate dimensions.
		scope_types = validate_scope_rows(self, "pricing_rule_priority")

		# This table must cover every dimension exactly once.
		if set(scope_types) != set(SCOPE_TYPES):
			frappe.throw(
				_("Pricing Rule Priority must list each scope dimension exactly once: {0}.").format(
					", ".join(SCOPE_TYPES)
				),
				title=_("Incomplete Pricing Rule Priority"),
			)

		# Priority ranks must be exactly {1, 2, 3}, each used once.
		priorities = []
		for row in rows:
			if str(row.priority) not in PRIORITY_VALUES:
				frappe.throw(
					_("Row #{0}: Priority must be one of: {1}.").format(
						row.idx, ", ".join(PRIORITY_VALUES)
					),
					title=_("Invalid Priority"),
				)
			priorities.append(str(row.priority))

		if set(priorities) != set(PRIORITY_VALUES):
			frappe.throw(
				_("Each priority rank ({0}) must be assigned to exactly one dimension.").format(
					", ".join(PRIORITY_VALUES)
				),
				title=_("Duplicate Priority"),
			)
