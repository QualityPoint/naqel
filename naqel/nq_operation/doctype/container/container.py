# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import base64
import io

import frappe
from frappe import _
from frappe.model.document import Document
from naqel.utils.geolocation import sync_geolocation_to_floats


class Container(Document):
    def validate(self):
        sync_geolocation_to_floats(
            self, geolocation_field="container_location")
        self.validate_fill_level()
        if not self.is_new() and self.has_value_changed("container_id"):
            self._set_qr_code()

    def after_insert(self):
        self.generate_qr_code()

    def after_rename(self, _old, _new, _merge=False):
        self.generate_qr_code()

    def validate_fill_level(self):
        if not self.fill_level:
            default_fill_level = frappe.db.get_value(
                "Container Fill Level", {"is_default": 1})
            if default_fill_level:
                self.fill_level = default_fill_level

        if self.fill_level:
            fill_level_doc = frappe.db.get_value(
                "Container Fill Level", self.fill_level, ["name", "disabled"], as_dict=True
            )
            if fill_level_doc:
                if fill_level_doc.disabled:
                    frappe.throw(
                        _("The Fill Level {0} is disabled. Please select another one.").format(
                            fill_level_doc.name
                        )
                    )
            else:
                frappe.throw(
                    _("The Fill Level {0} does not exist. Please select a valid one.").format(
                        self.fill_level
                    )
                )

    @property
    def qr_image_src(self) -> str | None:
        if not self.qr_code:
            return None
        import qrcode

        qr = qrcode.QRCode(version=1, box_size=4, border=4)
        qr.add_data(self.qr_code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, kind="PNG")
        buffer.seek(0)
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")

    def set_qr_code(self):
        self.qr_code = f"{self.name}|{self.container_id}"

    def generate_qr_code(self):
        self.set_qr_code()
        frappe.db.set_value(self.doctype, self.name, "qr_code", self.qr_code)


@frappe.whitelist()
def generate_qr_code(name):
    doc = frappe.get_doc("Container", name)
    doc.generate_qr_code()
    return True


@frappe.whitelist()
def scan_container_qr(barcode):
    name = frappe.db.get_value("Container", {"qr_code": barcode})
    if not name:
        frappe.throw(_("No container found for QR code: {0}").format(barcode))
    return frappe.db.get_value(
        "Container",
        name,
        ["name",
         "container_id",
         "container_type",
         "operational_status",
         "condition",
         "fill_level"
         ],
        as_dict=True,
    )
