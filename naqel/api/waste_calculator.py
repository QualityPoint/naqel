# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

"""
Waste Calculator Public API
Lightweight API wrappers for guest access - all business logic in doctype file
"""

import frappe
from frappe import _
import json

# Import all calculation functions from doctype
from naqel.nq_setup.doctype.waste_calculator.waste_calculator import (
    calculate_waste as _calculate_waste,
    get_service_type_details as _get_service_type_details,
    get_facility_uom_details as _get_facility_uom_details,
    get_service_configuration as _get_service_configuration,
    get_allowed_facility_uoms as _get_allowed_facility_uoms,
    get_facility_uom_hierarchy as _get_facility_uom_hierarchy,
    get_allowed_waste_types as _get_allowed_waste_types,
    get_leaf_descendants
)


# ============================================================================
# MAIN CALCULATION API
# ============================================================================

@frappe.whitelist(allow_guest=True)
def calculate_waste(doc, language=None):
    """
    Public API: Calculate waste generation for a facility

    Args:
        doc (dict): Waste Calculator document as dict/JSON
        language (str): Language code (e.g., 'ar' for Arabic, 'en' for English)

    Returns:
        dict: Calculation results including waste generation and container suggestions
    """
    # Set language context if provided
    if language:
        frappe.local.lang = language

    return _calculate_waste(doc)


# ============================================================================
# CONFIGURATION & UTILITY API METHODS
# ============================================================================

@frappe.whitelist(allow_guest=True)
def get_service_type_details(service_type):
    """
    Public API: Fetch service type details

    Args:
        service_type (str): Name of the Service Type

    Returns:
        dict: Service type fields (service_license)
    """
    return _get_service_type_details(service_type)


@frappe.whitelist(allow_guest=True)
def get_facility_uom_details(facility_uom):
    """
    Public API: Fetch facility UOM details

    Args:
        facility_uom (str): Name of the Facility UOM

    Returns:
        dict: Facility UOM fields (must_be_whole_number, is_composite_uom)
    """
    return _get_facility_uom_details(facility_uom)


@frappe.whitelist(allow_guest=True)
def get_service_configuration(isic_classification, service_type):
    """
    Public API: Get waste distributions from Service Configuration

    Args:
        isic_classification (str): ISIC Classification name
        service_type (str): Service Type name

    Returns:
        dict: waste_distributions and service_configuration name
    """
    return _get_service_configuration(isic_classification, service_type)


@frappe.whitelist(allow_guest=True)
def get_allowed_facility_uoms(service_configuration):
    """
    Public API: Get allowed Facility UOMs from Service Configuration

    Args:
        service_configuration (str): Service Configuration name

    Returns:
        list: List of allowed Facility UOM names
    """
    return _get_allowed_facility_uoms(service_configuration)


@frappe.whitelist(allow_guest=True)
def get_facility_uom_hierarchy(facility_uom):
    """
    Public API: Get all subsidiary UOMs from a composite Facility UOM

    Args:
        facility_uom (str): Facility UOM name

    Returns:
        list: List of dicts with UOM details (name, must_be_whole_number)
    """
    return _get_facility_uom_hierarchy(facility_uom)


@frappe.whitelist(allow_guest=True)
def get_allowed_waste_types(waste_types):
    """
    Public API: Get all leaf waste types that are descendants of the waste_types

    Args:
        waste_types (str): JSON string of waste_type names

    Returns:
        list: List of allowed leaf Waste Type objects with full details
    """
    return _get_allowed_waste_types(waste_types)


# ============================================================================
# PUBLIC API METHODS FOR GUEST ACCESS (Waste Calculator Frontend)
# ============================================================================

@frappe.whitelist(allow_guest=True)
def get_public_service_types(search=None):
    """
    Public API: Get all Service Types for public waste calculator

    Returns:
        dict: Response with service types data
    """
    try:
        filters = {}
        if search:
            filters['service_name'] = ['like', f'%{search}%']

        service_types = frappe.get_all(
            'Service Type',
            filters=filters,
            fields=['name', 'service_name'],
            order_by='service_name asc',
            limit=30
        )

        for item in service_types:
            item['service_name'] = frappe._(item['service_name'])

        return {
            "success": True,
            "data": service_types
        }

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Public Service Types Fetch Error"
        )
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist(allow_guest=True)
def get_public_isic_classifications(search=None):
    """
    Public API: Get all ISIC classifications (Activity level only)

    Returns:
        dict: Response with ISIC classifications data
    """
    try:
        filters = {
            'is_group': 0,
            'category_classification': 'Activity'
        }
        if search:
            filters['category_name'] = ['like', f'%{search}%']

        classifications = frappe.get_all(
            'ISIC Classification',
            filters=filters,
            fields=[
                'name',
                'category_code',
                'category_name'
            ],
            order_by='category_name asc',
            limit=30
        )

        for item in classifications:
            item['category_name'] = frappe._(item['category_name'])

        return {
            "success": True,
            "data": classifications
        }

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Public ISIC Classifications Fetch Error"
        )
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist(allow_guest=True)
def get_public_facility_uoms(service_configuration=None, search=None):
    """
    Public API: Get Facility UOMs for public waste calculator
    Optionally filtered by Service Configuration

    Args:
        service_configuration (str, optional): Service Configuration name to filter allowed UOMs
        search (str, optional): Search term to filter by uom_name

    Returns:
        dict: Response with facility UOMs data
    """
    try:
        # If service_configuration provided, get allowed UOMs
        if service_configuration:
            allowed_uoms = _get_allowed_facility_uoms(service_configuration)
            if allowed_uoms:
                uom_filters = {'name': ['in', allowed_uoms]}
                if search:
                    uom_filters['uom_name'] = ['like', f'%{search}%']
                uoms = frappe.get_all(
                    'Facility UOM',
                    filters=uom_filters,
                    fields=['name', 'uom_name', 'is_composite_uom',
                            'must_be_whole_number'],
                    order_by='uom_name asc',
                    limit=30
                )
            else:
                # No allowed UOMs - return empty
                return {
                    "success": True,
                    "data": []
                }
        else:
            # No filter - return all (with optional search)
            uom_filters = {}
            if search:
                uom_filters['uom_name'] = ['like', f'%{search}%']
            uoms = frappe.get_all(
                'Facility UOM',
                filters=uom_filters,
                fields=['name', 'uom_name', 'is_composite_uom',
                        'must_be_whole_number'],
                order_by='uom_name asc',
                limit=30
            )

        for item in uoms:
            item['uom_name'] = frappe._(item['uom_name'])

        return {
            "success": True,
            "data": uoms
        }

    except Exception as e:
        frappe.log_error(
            message=str(e),
            title="Public Facility UOMs Fetch Error"
        )
        return {
            "success": False,
            "message": str(e),
            "data": []
        }


@frappe.whitelist(allow_guest=True)
def get_public_service_configurations(service_type=None, isic_classification=None,
                                      territory=None, calculation_based_on=None, search=None):
    """Public API: configurations for the picker, matching the service type and the
    facility's ISIC walk (+ territory for Regional). Returns {name, label} rows."""
    try:
        if not service_type:
            return {"success": True, "data": []}

        from naqel.utils.waste_calculations import get_isic_ancestors

        ancestors = get_isic_ancestors(isic_classification, fetch_all=True) if isic_classification else []

        if calculation_based_on == 'Regional Service Configuration':
            data = _public_regional_configs(service_type, ancestors, territory, search)
        else:
            data = _public_service_configs(service_type, ancestors, search)

        return {"success": True, "data": data}

    except Exception as e:
        frappe.log_error(message=str(e), title="Public Service Configurations Fetch Error")
        return {"success": False, "message": str(e), "data": []}


def _public_service_configs(service_type, ancestors, search):
    SC = frappe.qb.DocType("Service Configuration")
    query = (
        frappe.qb.from_(SC)
        .select(SC.name, SC.title)
        .where(SC.disabled == 0)
        .where(SC.service_type == service_type)
    )
    if ancestors:
        query = query.where((SC.is_general_configuration == 1) | (SC.isic_classification.isin(ancestors)))
    else:
        query = query.where(SC.is_general_configuration == 1)
    if search:
        query = query.where(SC.name.like(f"%{search}%"))

    rows = query.limit(30).run(as_dict=True)
    for row in rows:
        row["label"] = frappe._(row.get("title")) if row.get("title") else row["name"]
    return rows


def _public_regional_configs(service_type, ancestors, territory, search):
    if not territory:
        return []
    node = frappe.db.get_value("Address Division", territory, ["lft", "rgt"], as_dict=True)
    if not node:
        return []
    divisions = frappe.db.sql_list(
        "SELECT name FROM `tabAddress Division` WHERE lft <= %s AND rgt >= %s",
        (node.lft, node.rgt),
    )
    if not divisions:
        return []

    RSC = frappe.qb.DocType("Regional Service Configuration")
    SC = frappe.qb.DocType("Service Configuration")
    query = (
        frappe.qb.from_(RSC)
        .join(SC).on(SC.name == RSC.service_configuration)
        .select(RSC.name, RSC.title)
        .where(RSC.disabled == 0)
        .where(RSC.service_type == service_type)
        .where(RSC.division.isin(divisions))
    )
    if ancestors:
        query = query.where((SC.is_general_configuration == 1) | (RSC.isic_classification.isin(ancestors)))
    else:
        query = query.where(SC.is_general_configuration == 1)
    if search:
        query = query.where(RSC.name.like(f"%{search}%"))

    rows = query.limit(30).run(as_dict=True)
    for row in rows:
        row["label"] = frappe._(row.get("title")) if row.get("title") else row["name"]
    return rows


@frappe.whitelist(allow_guest=True)
def get_public_address_divisions(search=None, division_category=None):
    """Public API: Address Divisions for the division picker, optionally scoped to a
    division category (Province / City / Municipality / District). Returns {name, label}."""
    try:
        filters = {}
        if division_category:
            filters["division_category"] = division_category
        if search:
            filters["division_name"] = ["like", f"%{search}%"]
        rows = frappe.get_all(
            "Address Division",
            filters=filters,
            fields=["name", "division_name"],
            order_by="division_name asc",
            limit=30,
        )
        for row in rows:
            row["label"] = row["division_name"]
        return {"success": True, "data": rows}

    except Exception as e:
        frappe.log_error(message=str(e), title="Public Address Divisions Fetch Error")
        return {"success": False, "message": str(e), "data": []}
