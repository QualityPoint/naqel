# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from naqel.utils import waste_calculations


class RegionalServiceConfiguration(Document):
    def before_validate(self):
        self.set_title()
        # Only run calculations when in Reconfiguration mode
        if self.configuration_method == "Reconfiguration":
            self.set_missing_values()
            self.calculate_child_table_volumes()
            self.calculate_threshold_statistics()
            self.calculate_volume_statistics()
            self.calculate_generation_rates()
        waste_calculations.sort_and_validate_ratings(self)

    def set_title(self):
        """Title: '<ISIC Classification> | <Division name>'."""
        division_name = frappe.db.get_value(
            "Address Division", self.division, "division_name") if self.division else None
        parts = [part for part in (self.isic_classification, division_name) if part]
        if parts:
            self.title = " | ".join(parts)

    def validate(self):
        self.validate_address_division()
        self.validate_unique_regional_configuration()

    def set_missing_values(self):
        """Set default values from Naqel Settings if not already set"""
        if not self.default_volume_unit:
            self.default_volume_unit = frappe.db.get_single_value(
                "Naqel Settings", "default_volume_unit"
            )

    def calculate_child_table_volumes(self):
        """Calculate volumes in child table before parent statistics"""
        waste_calculations.calculate_child_table_volumes(
            self, "default_volume_unit")

    def get_volume_conversion_factor(self, from_uom, to_uom):
        """Get conversion factor from one UOM to another
        Note: All conversions in UOM Conversion Factor use Litre as the base unit"""
        return waste_calculations.get_volume_conversion_factor(from_uom, to_uom)

    def calculate_threshold_statistics(self):
        """Calculate mean and median thresholds from generation classification"""
        waste_calculations.calculate_threshold_statistics(self)

    def calculate_volume_statistics(self):
        """Calculate mean and median volumes from generation classification"""
        waste_calculations.calculate_volume_statistics(
            self, "total_converted_volume")

    def calculate_generation_rates(self):
        """Calculate unit generation rate based on calculate_by selection"""
        waste_calculations.calculate_unit_generation_rate(self)

    def validate_address_division(self):
        if self.division_category and self.division:
            category = frappe.get_value(
                "Address Division", self.division, "division_category")

            if category != self.division_category:
                frappe.throw(_(
                    "The selected Division '{0}' is of Division Type '{1}', which does not match the Configuration By '{2}'"
                ).format(self.division, category, self.division_category))

    def validate_unique_regional_configuration(self):
        """Ensure unique combination of division_category, region, service_type, and isic_classification"""
        existing = frappe.db.exists(
            "Regional Service Configuration",
            {
                "division_category": self.division_category,
                "division": self.division,
                "service_type": self.service_type,
                "isic_classification": self.isic_classification,
                "name": ("!=", self.name)
            }
        )

        if existing:
            frappe.throw(
                _("Regional Service Configuration already exists for Division '{0}', Service Type '{1}', and ISIC Classification '{2}'").format(
                    self.division, self.service_type, self.isic_classification
                )
            )


@frappe.whitelist()
def get_service_configuration_data(service_type, isic_classification):
    """
    Get the original Service Configuration data to populate Regional Service Configuration

    Args:
        service_type: Name of the Service Type
        isic_classification: Name of the ISIC Classification

    Returns:
        dict: Service Configuration data including all fields and child tables
    """
    if not service_type or not isic_classification:
        frappe.throw(
            _("Both Service Type and ISIC Classification are required"))

    # Find the Service Configuration
    config_name = frappe.db.get_value(
        "Service Configuration",
        {
            "service_type": service_type,
            "isic_classification": isic_classification
        }
    )

    if not config_name:
        frappe.throw(
            _("No Service Configuration found for Service Type '{0}' and ISIC Classification '{1}'").format(
                service_type, isic_classification
            )
        )

    # Get the full document
    config_doc = frappe.get_doc("Service Configuration", config_name)

    # Prepare generation classification data
    generation_classification = []
    if config_doc.generation_classification:
        for gen_row in config_doc.generation_classification:
            generation_classification.append({
                "max_threshold": gen_row.max_threshold,
                "container_type": gen_row.container_type,
                "container_standard_volume": gen_row.container_standard_volume,
                "container_volume_unit": gen_row.container_volume_unit,
                "count": gen_row.count,
                "total_volume": gen_row.total_volume,
                "conversion_factor": gen_row.conversion_factor,
                "container_converted_volume": gen_row.container_converted_volume,
                "total_converted_volume": gen_row.total_converted_volume
            })

    # Prepare ratings data
    ratings = []
    if config_doc.ratings:
        for rating_row in config_doc.ratings:
            ratings.append({
                "rating": rating_row.rating,
                "safety_factor": rating_row.safety_factor
            })

    return {
        "generation_classification": generation_classification,
        "mean_threshold": config_doc.mean_threshold,
        "median_threshold": config_doc.median_threshold,
        "mean_volume": config_doc.mean_volume,
        "median_volume": config_doc.median_volume,
        "default_volume_unit": config_doc.default_volume_unit,
        "mean_generation_rate": config_doc.mean_generation_rate,
        "median_generation_rate": config_doc.median_generation_rate,
        "calculate_facility_wastes_by": config_doc.calculate_facility_wastes_by,
        "calculate_generation_rate_by": config_doc.calculate_generation_rate_by,
        "ratings": ratings
    }
