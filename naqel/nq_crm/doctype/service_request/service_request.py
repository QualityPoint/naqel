# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from naqel.utils.party import (
    clear_milestone_fields,
    set_conversion_factor,
    set_customer_name,
    set_net_facility_measurement,
    validate_duration_fields,
    validate_facility_belongs_to_party,
)


class ServiceRequest(Document):
    def before_validate(self):
        clear_milestone_fields(self, duration_field="service_duration", clear_when_milestone=True)
        self.set_waste_configuration()
        set_conversion_factor(self)
        set_net_facility_measurement(self)

    def set_waste_configuration(self):
        if not self.service_type or not self.isic_classification:
            return

        from naqel.nq_crm.doctype.service_quotation.service_quotation import (
            resolve_waste_configuration,
        )

        based_on, config = resolve_waste_configuration(
            self.service_type, self.isic_classification, self.territory
        )
        if based_on:
            self.calculation_based_on = based_on
        if config:
            self.service_configuration = config

    def validate(self):
        self.validate_request_from()
        validate_facility_belongs_to_party(self, "request_from", "party")
        validate_duration_fields(self, required_when_not_milestone=True)
        set_customer_name(self, "request_from", "party")

    def validate_request_from(self):
        if self.request_from and self.request_from not in ("Customer", "Lead"):
            frappe.throw(
                _("Request From must be {0}.").format("Customer or Lead")
            )
