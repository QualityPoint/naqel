import frappe
from frappe import _
from frappe.desk.page.setup_wizard.setup_wizard import make_records
import csv
import os
import json
from pathlib import Path

from naqel.utils.address_template.setup import set_up_address_templates
from naqel.custom.isic import make_isic_fixtures
from naqel.custom.fixture_utils import make_fixtures_from_json


def make_fixtures():
    """Create default fixture data for the app"""
    records = [
        # facility uom
        {
            "doctype": "Facility UOM",
            "uom_name": _("Individual"),
            "enabled": 1,
            "must_be_whole_number": 1,
            "default_uom": "Nos"
        },
        {
            "doctype": "Facility UOM",
            "uom_name": _("Area"),
            "enabled": 1,
            "must_be_whole_number": 0,
            "default_uom": "Square Meter"
        },
        # identification number
        {
            "doctype": "Identification Number",
            "id_type": _("VAT Registration Number"),
            "id_code": "VAT",
        },
        {
            "doctype": "Identification Number",
            "id_type": _("Commercial Registration Number"),
            "id_code": "CRN",
        },
        {
            "doctype": "Identification Number",
            "id_type": _("Tax Identification Number"),
            "id_code": "TIN",
        },
        {
            "doctype": "Identification Number",
            "id_type": _("700 Number"),
            "id_code": "700",
        },
        {
            "doctype": "Identification Number",
            "id_type": _("National ID"),
            "id_code": "NAT",
        },
        {
            "doctype": "Identification Number",
            "id_type": _("Iqama"),
            "id_code": "IQA",
        },
        # container fill level
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Overflowing"),
            "disabled": 0,
            "color": "#7E0000",
            "is_default": 0,
            "is_collection_trigger": 1
        },
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Full"),
            "disabled": 0,
            "color": "#FF0000",
            "is_default": 0,
            "is_collection_trigger": 1
        },
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Three Quarters"),
            "disabled": 0,
            "color": "#FFA500",
            "is_default": 0,
            "is_collection_trigger": 0
        },
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Half"),
            "disabled": 0,
            "color": "#FFFF00",
            "is_default": 0,
            "is_collection_trigger": 0
        },
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Quarter"),
            "disabled": 0,
            "color": "#00FF00",
            "is_default": 0,
            "is_collection_trigger": 0
        },
        {
            "doctype": "Container Fill Level",
            "fill_level": _("Empty"),
            "disabled": 0,
            "color": "#808080",
            "is_default": 1,
            "is_collection_trigger": 0
        },
    ]

    # Now create other fixtures
    make_records(records)

    # Service fixtures
    make_fixtures_from_json(
        "License Type", "service_license_data.json", "license_name")
    make_fixtures_from_json(
        "Service Type", "service_type_data.json", "service_name")

    # Waste and ISIC fixtures
    make_fixtures_from_json("Waste Type", "waste_type_data.json", "waste_name")
    make_isic_fixtures()

    set_up_address_templates(default_country="Saudi Arabia")
