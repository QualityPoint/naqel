# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from naqel.utils import waste_calculations


class ServiceConfiguration(Document):
    def before_validate(self):
        self.handle_general_configuration()
        self.set_title()
        self.set_missing_values()
        self.populate_service_type_details()
        self.calculate_child_table_volumes()
        self.calculate_threshold_statistics()
        self.calculate_volume_statistics()
        self.calculate_generation_rates()
        waste_calculations.sort_and_validate_ratings(self)

    def handle_general_configuration(self):
        """Clear ISIC fields if general configuration is enabled"""
        if self.is_general_configuration:
            self.isic_classification_category = None
            self.isic_classification = None

    def set_title(self):
        """Auto-generate name based on service type and ISIC classification"""
        if self.is_general_configuration:
            self.title = f"GC - {self.service_type}"
        else:
            self.title = f"{self.isic_classification}"

    def set_missing_values(self):
        """Set default values from Naqel Settings if not already set"""
        if not self.default_volume_unit:
            self.default_volume_unit = frappe.db.get_single_value(
                "Naqel Settings", "default_volume_unit"
            )

    def populate_service_type_details(self):
        """Populate fields from Service Type if not already set"""
        if not self.service_type:
            return

        # Get waste type details from Service Type
        details = get_waste_types(self.service_type)

        if not details:
            return

        # Populate waste distributions if not already populated
        if not self.waste_distributions and details.get("waste_distributions"):
            for waste_dist in details.get("waste_distributions", []):
                self.append("waste_distributions", {
                    "waste_type": waste_dist.get("waste_type"),
                    "is_group": waste_dist.get("is_group")
                })

    def calculate_child_table_volumes(self):
        """Calculate volumes in child table before parent statistics"""
        waste_calculations.calculate_child_table_volumes(
            self, "default_volume_unit")

    def get_volume_conversion_factor(self, from_uom, to_uom):
        """Get conversion factor from one UOM to another
        Note: All conversions in UOM Conversion Factor use Litre as the base unit"""
        return waste_calculations.get_volume_conversion_factor(from_uom, to_uom)

    def validate(self):
        self.validate_general_service_configuration()
        self.validate_unique_service_by_category()
        self.validate_waste_distribution_percentages()

    def validate_general_service_configuration(self):
        """Validate that only one general configuration exists per service type"""
        if self.is_general_configuration:
            # Check if another general configuration already exists for this service type
            existing = frappe.db.exists(
                "Service Configuration",
                {
                    "service_type": self.service_type,
                    "is_general_configuration": 1,
                    "name": ("!=", self.name)
                }
            )

            if existing:
                frappe.throw(
                    _("A General Configuration already exists for Service Type '{0}'. Only one general configuration is allowed per service type.").format(
                        frappe.bold(self.service_type)
                    ),
                    title=_("Duplicate General Configuration")
                )

    def validate_unique_service_by_category(self):
        """Ensure unique combination of service_type and isic_classification"""
        # Skip this validation for general configurations (no ISIC classification)
        if self.is_general_configuration:
            return

        existing = frappe.db.exists(
            "Service Configuration",
            {
                "service_type": self.service_type,
                "isic_classification": self.isic_classification,
                "name": ("!=", self.name)
            }
        )

        if existing:
            frappe.throw(
                _("Service Configuration already exists for Service Type '{0}' and ISIC Classification '{1}'").format(
                    self.service_type, self.isic_classification
                )
            )

    def validate_waste_distribution_percentages(self):
        """Validate that waste distribution percentages sum to approximately 100%"""
        if self.waste_distributions:
            total_percentage = sum(
                row.distribution_percentage or 0 for row in self.waste_distributions)

            # Allow tolerance of 0.1% for rounding (e.g., 33.33 + 33.33 + 33.33 = 99.99)
            tolerance = 0.1

            if abs(total_percentage - 100) > tolerance:
                frappe.throw(
                    _("Total waste distribution percentage must equal 100%. Current total: {0}%").format(
                        frappe.format(total_percentage, {
                            "fieldtype": "Float", "precision": 2})
                    )
                )

    def calculate_threshold_statistics(self):
        """Calculate mean and median thresholds from generation classification"""
        waste_calculations.calculate_threshold_statistics(self)

    def calculate_volume_statistics(self):
        """Calculate mean and median volumes from generation classification"""
        waste_calculations.calculate_volume_statistics(
            self, "total_converted_volume")

    def calculate_generation_rates(self):
        """Calculate mean and median generation rates (volume per unit threshold)"""
        waste_calculations.calculate_generation_rates(self)


@frappe.whitelist()
def get_waste_types(service_type):
    """
    Get waste type distributions for a service type.

    Args:
        service_type: Name of the Service Type

    Returns:
        dict: Contains waste_distributions list with waste_type and is_group
    """
    if not service_type:
        return {"waste_distributions": []}

    doc = frappe.get_doc("Service Type", service_type)

    # Waste types always live in the `wastes` child table (one or many rows).
    waste_distributions = [
        {
            "waste_type": row.waste_type,
            "is_group": row.is_group
        }
        for row in doc.wastes
    ]

    return {"waste_distributions": waste_distributions}


@frappe.whitelist()
def get_facility_default_uom(facility_uom):
    """
    Get the default unit of measure for a facility.
    Args:
        facility_uom: Name of the Facility UOM

    Returns:
        str: Default UOM for the facility   
    """
    return frappe.db.get_value("Facility UOM", facility_uom, "default_uom")


@frappe.whitelist()
def get_uom_conversion_factor(from_uom, to_uom):
    """
    Get conversion factor from one UOM to another
    Note: All conversions in UOM Conversion Factor use Litre as the base unit

    Args:
        from_uom: Source UOM
        to_uom: Target UOM

    Returns:
        float: Conversion factor
    """
    if not from_uom or not to_uom:
        frappe.throw(_("Both From UOM and To UOM are required"))

    if from_uom == to_uom:
        return 1.0

    # Try direct conversion (from Litre to target)
    if from_uom == "Litre":
        conversion = frappe.db.get_value(
            "UOM Conversion Factor",
            {"from_uom": "Litre", "to_uom": to_uom},
            "value"
        )
        if conversion:
            return float(conversion)

    # Try reverse conversion (target is Litre)
    if to_uom == "Litre":
        conversion = frappe.db.get_value(
            "UOM Conversion Factor",
            {"from_uom": "Litre", "to_uom": from_uom},
            "value"
        )
        if conversion:
            return 1.0 / float(conversion)

    # For conversions between non-Litre units, calculate through Litre as intermediate
    # Convert: from_uom → Litre → to_uom
    # Formula: (Litre_to_to_uom) / (Litre_to_from_uom)
    from_uom_factor = frappe.db.get_value(
        "UOM Conversion Factor",
        {"from_uom": "Litre", "to_uom": from_uom},
        "value"
    )

    to_uom_factor = frappe.db.get_value(
        "UOM Conversion Factor",
        {"from_uom": "Litre", "to_uom": to_uom},
        "value"
    )

    if from_uom_factor and to_uom_factor:
        # Conversion factor = to_uom_factor / from_uom_factor
        return float(to_uom_factor) / float(from_uom_factor)

    # No conversion found - throw error
    frappe.throw(
        _("No conversion factor found between {0} and {1}. Please add it in UOM Conversion Factor.").format(
            frappe.bold(from_uom),
            frappe.bold(to_uom)
        )
    )


@frappe.whitelist()
def get_leaf_waste_types(waste_type):
    """Return all non-group descendants of ``waste_type`` using the nested-set
    (lft / rgt) index that Frappe maintains on tree doctypes.

    When the node itself is not a group (is_group == 0) it is returned as the
    only element — it IS the leaf.  When it is a group, all descendants with
    is_group == 0 are returned, sorted alphabetically by name.

    Args:
        waste_type (str): Name of the Waste Type node to expand.

    Returns:
        list[str]: Sorted list of leaf Waste Type names.
    """
    if not waste_type:
        return []

    node = frappe.db.get_value("Waste Type", waste_type, ["lft", "rgt", "is_group"], as_dict=True)
    if not node:
        return []

    # Leaf node — return itself
    if not node.is_group:
        return [waste_type]

    # Group node — fetch all non-group descendants within the lft/rgt window
    leaves = frappe.get_all(
        "Waste Type",
        filters={
            "lft": (">", node.lft),
            "rgt": ("<", node.rgt),
            "is_group": 0,
        },
        pluck="name",
        order_by="name",
    )
    return leaves
