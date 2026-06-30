# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FacilityUOM(Document):
    def validate(self):
        self.validate_default_uom()
        self.validate_composite_uom()

    def validate_default_uom(self):
        if self.default_uom:
            uom = frappe.get_doc("UOM", self.default_uom)
            if not uom.enabled:
                frappe.throw(
                    _("The selected Default UOM '{0}' is disabled").format(
                        self.default_uom
                    )
                )
            if self.must_be_whole_number != uom.must_be_whole_number:
                frappe.throw(
                    _("The selected Default UOM '{0}' must have the same 'Must Be Whole Number' setting as '{1}'").format(
                        self.default_uom, self.must_be_whole_number
                    )
                )

        else:
            frappe.throw(_("Please select a Default UOM."))

    def validate_composite_uom(self):
        if self.is_composite_uom:
            if not self.subsidiary_uom:
                frappe.throw(
                    _("Please select a Subsidiary UOM for Composite UOM."))
            if self.subsidiary_uom == self.name:
                frappe.throw(
                    _("Subsidiary UOM cannot be the same as the main UOM for Composite UOM."))
