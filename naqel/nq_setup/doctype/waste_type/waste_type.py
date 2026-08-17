# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet, get_descendants_of

from naqel.utils.uom import validate_uom_field


class WasteType(NestedSet):
    def validate(self):
        if not self.parent_waste_type and not frappe.flags.in_test:
            if frappe.db.exists("Waste Type", _("All Waste Types")):
                self.parent_waste_type = _("All Waste Types")
        validate_uom_field(self, "waste_density_unit", "Density")

    def on_update(self):
        NestedSet.on_update(self)
        self.validate_one_root()
        self.delete_child_waste_types_key()

    def on_trash(self):
        NestedSet.on_trash(self, allow_root_deletion=True)
        self.delete_child_waste_types_key()

    def delete_child_waste_types_key(self):
        frappe.cache().hdel("child_waste_types", self.name)

    @frappe.whitelist()
    def calculate_average_density(self):
        """Calculate average density from all leaf descendants with unit conversion"""
        if not self.is_group:
            frappe.throw(
                _("This method can only be called for parent waste types"))

        # Get standard density unit from Naqel Settings
        standard_unit = frappe.db.get_single_value(
            "Naqel Settings", "default_density_unit")
        if not standard_unit:
            frappe.throw(
                _("Please set the Default Density Unit in Naqel Settings"))

        # Get all descendants using nested set
        descendants = frappe.get_all(
            "Waste Type",
            filters={
                "lft": (">", self.lft),
                "rgt": ("<", self.rgt),
                "is_group": 0,
                "waste_standard_density": (">", 0)
            },
            fields=["waste_standard_density", "waste_density_unit"]
        )

        if not descendants:
            frappe.msgprint(_("No leaf descendants with density found"))
            return

        # Convert all densities to standard unit and calculate average
        total_density = 0.0
        for d in descendants:
            density_value = d.waste_standard_density

            # Convert to standard unit if different
            if d.waste_density_unit and d.waste_density_unit != standard_unit:
                density_value = convert_density_unit(
                    density_value,
                    d.waste_density_unit,
                    standard_unit
                )

            if density_value is not None:
                total_density += density_value

        avg_density = total_density / len(descendants)

        # Update the current document
        self.waste_standard_density = avg_density
        self.waste_density_unit = standard_unit
        self.save()

        frappe.msgprint(_("Average density calculated: {0}").format(
            frappe.format(avg_density, {"fieldtype": "Float"})))


def convert_density_unit(value, from_unit, to_unit):
    """Convert density value from one unit to another using UOM Conversion Factor"""
    if from_unit == to_unit:
        return value

    # Try direct conversion
    conversion = frappe.db.get_value(
        "UOM Conversion Factor",
        {"from_uom": from_unit, "to_uom": to_unit},
        "value"
    )

    if conversion:
        return value * conversion

    # Try reverse conversion
    reverse_conversion = frappe.db.get_value(
        "UOM Conversion Factor",
        {"from_uom": to_unit, "to_uom": from_unit},
        "value"
    )

    if reverse_conversion:
        return value / reverse_conversion

    frappe.throw(_("No conversion factor found between {0} and {1}").format(
        from_unit, to_unit))


def get_child_waste_types(waste_type_name):
    waste_type = frappe.get_cached_value(
        "Waste Type", waste_type_name, ["lft", "rgt"], as_dict=1)

    child_waste_types = [
        d.name
        for d in frappe.get_all(
            "Waste Type", filters={"lft": (">=", waste_type.lft), "rgt": ("<=", waste_type.rgt)}
        )
    ]

    return child_waste_types or {}
