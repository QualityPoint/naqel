# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceType(Document):
    def validate(self):
        self.validate_item()

    def validate_item(self):
        """Ensure the linked Item is a service item (not stock, not a variant template, not a fixed asset)."""
        if not self.item:
            return
        item = frappe.db.get_value(
            "Item",
            self.item,
            ["is_stock_item", "has_variants", "is_fixed_asset"],
            as_dict=True,
        )
        if not item:
            return
        if item.is_stock_item:
            frappe.throw(
                _("Item {0} is a stock item. Only non-stock service items are allowed.").format(
                    frappe.bold(self.item)
                ),
                title=_("Invalid Item"),
            )
        if item.has_variants:
            frappe.throw(
                _("Item {0} is a template with variants. Please select a specific item variant.").format(
                    frappe.bold(self.item)
                ),
                title=_("Invalid Item"),
            )
        if item.is_fixed_asset:
            frappe.throw(
                _("Item {0} is a fixed asset. Only non-stock service items are allowed.").format(
                    frappe.bold(self.item)
                ),
                title=_("Invalid Item"),
            )
