# Copyright (c) 2025, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt
import json
import re
from naqel.utils.waste_calculations import get_isic_ancestors, get_volume_conversion_factor


class WasteCalculator(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_from_db(self):
        # 'modified' attribute is required for `run_doc_method` to work properly.
        doc_dict = frappe._dict(
            {
                "modified": None,
            }
        )
        super(Document, self).__init__(doc_dict)

    def save(self):
        return

    @staticmethod
    def get_list(args):
        pass

    @staticmethod
    def get_count(args):
        pass

    @staticmethod
    def get_stats(args):
        pass

    def db_insert(self, *args, **kwargs):
        pass

    def db_update(self, *args, **kwargs):
        pass

    def delete(self):
        pass


@frappe.whitelist()
def calculate_waste(doc):
    """
    Calculate waste generation for a facility based on Service Configuration

    Supports two calculation methods:
    1. Cluster Classification - Uses threshold ranges from generation_classification table
    2. Generation Rate - Direct multiplication with generation rate

    Args:
            doc (dict): Waste Calculator document as dict

    Returns:
            dict: Calculation results including waste generation and container suggestions
    """
    if isinstance(doc, str):
        doc = json.loads(doc)

    doc = frappe._dict(doc)

    # Validate required fields
    if not doc.service_type or not doc.isic_classification or not doc.facility_uom:
        frappe.throw(
            _("Please provide Service Type, ISIC Classification, and Facility UOM"))

    if not doc.calculation_based_on:
        frappe.throw(_("Please select Calculation Based On"))

    # Whether to project waste over day/week/month/year. This is a Waste Calculator
    # toggle set by the caller (Waste Calculator / public page); off by default.
    apply_service_duration = cint(doc.get('apply_service_duration'))

    # Validate that ISIC Classification exists and get its details
    isic_details = frappe.db.get_value(
        'ISIC Classification',
        doc.isic_classification,
        ['category_classification', 'is_group', 'name'],
        as_dict=1
    )

    if not isic_details:
        frappe.throw(_("Invalid ISIC Classification: {0}").format(
            doc.isic_classification))

    # Prefer leaf nodes (Activity level) for most accurate calculation
    # But allow any level - the system will traverse up to find configuration
    if isic_details.is_group:
        # Warn if using a group node, but don't block
        frappe.msgprint(
            _("You selected a Group-level ISIC classification ({0}). For more accurate results, consider selecting an Activity-level classification (leaf node).").format(
                isic_details.category_classification
            ),
            title=_("ISIC Selection Notice"),
            indicator='orange'
        )

    # Determine the configuration to compute from. When one is chosen in the form
    # (service_configuration + calculation_based_on), use it directly — separation of
    # concern — otherwise auto-resolve via the ISIC hierarchy. A Safety-Factor RSC
    # defers to its base SC and scales the result by its safety factor.
    safety_multiplier = 1
    chosen_config = doc.get('service_configuration')
    if chosen_config:
        service_config, safety_multiplier = resolve_calculation_config(
            doc.calculation_based_on, chosen_config
        )
        config_found_at = service_config.name
        config_found_level = doc.calculation_based_on
        checked_path = []
    else:
        config_result = _get_service_config_from_hierarchy(
            doc.isic_classification,
            doc.service_type
        )

        if not config_result:
            # Build helpful error message showing what was searched
            checked_levels = []
            current_check = doc.isic_classification
            while current_check:
                isic_info = frappe.db.get_value(
                    'ISIC Classification',
                    current_check,
                    ['category_classification', 'parent_category', 'category_code'],
                    as_dict=1
                )
                if isic_info:
                    checked_levels.append(
                        f"{isic_info.category_classification} ({isic_info.category_code})")
                    current_check = isic_info.parent_category
                else:
                    break

            error_msg = _("No Service Configuration found for Service Type '{0}' in the ISIC hierarchy.").format(
                doc.service_type
            )
            error_msg += "<br><br>" + \
                _("Searched hierarchy: {0}").format(" → ".join(checked_levels))
            error_msg += "<br><br>" + \
                _("Most Service Configurations are defined at <b>Group level</b>. Please ensure configurations exist for this industry.")

            frappe.throw(error_msg, title=_("Configuration Not Found"))

        service_config = config_result.get('config')
        config_found_at = config_result.get('found_at')
        config_found_level = config_result.get('found_level')
        checked_path = config_result.get('checked_path', [])

        if not service_config:
            frappe.throw(_("Configuration document not found"))

    # Facility UOM always comes from a Service Configuration. A Regional Service
    # Configuration carries none, so resolve to its base SC for the UOM; the compute
    # config (service_config) may still be the RSC for a Reconfiguration deviation.
    uom_source_config = (resolve_uom_config_doc(chosen_config) if chosen_config
                         else service_config) or service_config

    # Validate Facility UOM matches configuration
    if uom_source_config.facility_uom != doc.facility_uom:
        frappe.msgprint(
            _("Warning: Your Facility UOM ({0}) differs from the configuration's expected UOM ({1}). Results may be inaccurate.").format(
                doc.facility_uom, uom_source_config.facility_uom
            ),
            title=_("UOM Mismatch"),
            indicator='orange'
        )

    # Validate and auto-populate wastes based on waste_types
    validate_and_populate_wastes(doc, service_config)

    # Calculate facility measurement and apply conversion factor
    facility_measurement = calculate_facility_measurement(doc)

    if facility_measurement <= 0:
        frappe.throw(_("Facility measurement must be greater than 0"))

    conversion_factor = frappe.utils.flt(doc.get("conversion_factor")) or 1
    net_facility_measurement = facility_measurement * conversion_factor
    doc.net_facility_measurement = net_facility_measurement

    # Compute the base waste and apply the rating + regional safety factors. The config
    # is already resolved above; the shared helper owns the math (see Service Quotation).
    # The chosen config (an RSC for Regional basis) supplies the Rating Classification.
    calc_method = service_config.calculate_facility_wastes_by
    totals = compute_waste_totals(
        service_config,
        safety_multiplier,
        net_facility_measurement,
        doc,
        rating_config_name=chosen_config or service_config.name,
        facility_rating=doc.facility_rating,
    )
    calc_result = totals.calc_result
    facility_generated_waste = totals.facility_generated_waste
    rating_safety_factor = totals.rating_safety_factor
    regional_safety_factor = totals.regional_safety_factor
    total_generated_waste = totals.total_generated_waste

    # Container suggestion from generation_classification (daily basis). Use the
    # cluster's own container only when nothing scaled the waste; otherwise re-suggest
    # against the (scaled) total so capacity stays correct.
    if safety_multiplier == 1 and calc_result.get('container_type') and calc_result.get('container_count'):
        container_suggestion = {
            'container': calc_result.get('container_type'),
            'count': calc_result.get('container_count')
        }
    else:
        container_suggestion = suggest_container(
            total_generated_waste,
            service_config.default_volume_unit,
            service_config.name
        )

    # Suggested container rows (mirrors Service Quotation Container) — built before the
    # report so the breakdown can render a Suggested Containers section.
    generated_wastes = build_generated_container_rows(
        service_config,
        service_config.default_volume_unit,
        total_generated_waste,
        facility_generated_waste,
        calc_result.get('generation_rate', 0),
        regional_safety_factor,
        rating_safety_factor,
        service_type=doc.service_type,
        single_suggestion=container_suggestion,
        allocate_override=doc.get('allocate_container_for_each_waste_type'),
    )

    # Build calculation details HTML
    waste_calculation = build_calculation_details(
        net_facility_measurement,
        calc_result,
        rating_safety_factor,
        regional_safety_factor,
        facility_generated_waste,
        total_generated_waste,
        service_config,
        doc,
        apply_service_duration,
        generated_wastes,
    )

    # Configuration remarks with traversal information
    # Use title if available, otherwise fall back to name
    config_display = service_config.title or service_config.name
    config_remarks = _("Service Configuration: {0}").format(
        frappe.bold(_(config_display)))

    # Show which level's configuration is being used
    config_remarks += "\n" + _("Configuration Level: {0}").format(
        frappe.bold(_(config_found_level))
    )

    # Show if configuration was found at different level
    if config_found_at != doc.isic_classification:
        config_remarks += "\n" + _("Found at: {0}").format(
            frappe.bold(_(config_found_at))
        )

        # Show traversal path with codes for clarity
        path_items = []
        for p in checked_path:
            code_part = f"[{p['code']}]" if p.get('code') else ''
            path_items.append(f"{p['level']} {code_part}")

        path_str = " → ".join(path_items)
        config_remarks += "\n" + _("Search Path: {0}").format(path_str)

        # Helpful message
        config_remarks += "\n" + \
            frappe.bold(_("Note: ")) + \
            _("Configuration found at parent level in ISIC hierarchy.")

    config_remarks += "\n\n" + _("Calculation Method: {0}").format(
        frappe.bold(_(calc_method)))

    if calc_method == 'Cluster Classification':
        config_remarks += "\n" + _("Generation Rate Method: {0}").format(
            _(service_config.calculate_generation_rate_by)
        )
        config_remarks += "\n" + _("Facility UOM: {0}").format(
            _(uom_source_config.facility_uom)
        )

    # Show daily basis note only for recurring waste services
    if apply_service_duration:
        config_remarks += "\n\n" + \
            frappe.bold(_("All calculations are on DAILY basis"))

    # Calculate time-based estimates for recurring waste
    time_estimates = None
    if apply_service_duration:
        time_estimates = {
            'daily': total_generated_waste,
            'weekly': total_generated_waste * 7,
            'monthly': total_generated_waste * 30,
            'yearly': total_generated_waste * 365
        }

    return {
        'facility_unit_generation_rate': calc_result.get('generation_rate', 0),
        'regional_safety_factor': regional_safety_factor,
        'rating_safety_factor': rating_safety_factor,
        'facility_generated_waste': facility_generated_waste,
        'total_generated_waste': total_generated_waste,
        'suggested_container': container_suggestion.get('container'),
        'suggested_container_count': container_suggestion.get('count', 0),
        'generated_wastes': generated_wastes,
        'waste_calculation': waste_calculation,
        'configuration_remarks': config_remarks,
        'waste_unit': service_config.default_volume_unit,
        'apply_service_duration': apply_service_duration,
        'time_estimates': time_estimates
    }


def _get_service_config_from_hierarchy(isic_classification, service_type):
    """
    Private helper: Get service configuration based on ISIC and service type

    Priority order:
    1. Check for General Configuration (is_general_configuration=1) for the service type
    2. If not found, traverse ISIC hierarchy until a configuration is found

    Hierarchy traversal order: Activity → Category → Group → Division → Section
    Most Service Configurations are defined at Group level (224 configurations)

    Args:
        isic_classification: ISIC Classification name
        service_type: Service Type name

    Returns:
        dict: {
            'config': frappe._dict - Service Configuration document fields,
            'found_at': str - ISIC Classification name where config was found (or 'General' if general config),
            'found_level': str - Category classification level or 'General Configuration',
            'checked_path': list - List of ISIC names checked in order
        }
        None: If no configuration found at any level
    """

    # STEP 1: Check for General Configuration first (highest priority)
    general_config_name = frappe.db.get_value(
        'Service Configuration',
        {
            'disabled': 0,
            'is_general_configuration': 1,
            'service_type': service_type
        },
        'name'
    )

    if general_config_name:
        # General configuration found - load full document
        config = frappe.get_doc('Service Configuration', general_config_name)
        return {
            'config': config,
            'found_at': 'General',
            'found_level': 'General Configuration',
            'checked_path': [{
                'name': 'General Configuration',
                'level': 'General Configuration',
                'code': ''
            }]
        }

    # STEP 2: No general configuration found - traverse ISIC hierarchy
    # fetch_all=False: lazy parent_category walk, short-circuits on first match
    checked_path = []

    for current_isic in get_isic_ancestors(isic_classification, fetch_all=False):
        isic_details = frappe.db.get_value(
            'ISIC Classification',
            current_isic,
            ['category_classification', 'category_code'],
            as_dict=1
        )

        level_name = isic_details.category_classification if isic_details else 'Unknown'
        code = isic_details.category_code if isic_details else ''

        checked_path.append(
            {'name': current_isic, 'level': level_name, 'code': code})

        config_name = frappe.db.get_value(
            'Service Configuration',
            {'disabled': 0, 'isic_classification': current_isic,
                'service_type': service_type},
            'name'
        )

        if config_name:
            config = frappe.get_doc('Service Configuration', config_name)
            return {
                'config': config,
                'found_at': current_isic,
                'found_level': level_name,
                'checked_path': checked_path
            }

    return None


def get_leaf_descendants(waste_type):
    """
    Get all leaf (non-group) descendants of a waste type

    Args:
        waste_type (str): Waste Type name

    Returns:
        list: List of leaf waste type names
    """
    from frappe.utils.nestedset import get_descendants_of

    descendants = get_descendants_of(
        'Waste Type', waste_type, ignore_permissions=True)

    # Filter only leaf nodes (is_group=0) in a single query
    if not descendants:
        return []

    leaf_descendants = frappe.db.get_all(
        'Waste Type',
        filters={'name': ['in', descendants], 'is_group': 0},
        pluck='name'
    )

    return leaf_descendants


def _row_value(row, field):
    """Read a field from a child row whether it's a dict or a Document."""
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def parse_waste_items(value):
    """Split a comma/newline-joined Waste Item string into individual waste types."""
    if not value:
        return []
    return [part.strip() for part in re.split(r'[\n,]', value) if part.strip()]


def validate_and_populate_wastes(doc, service_config):
    """
    Validate and auto-populate wastes based on waste_types from Service Configuration

    Logic:
    - For leaf waste types (is_group=0): Auto-populate into wastes field
    - For group waste types (is_group=1): Validate user selected at least one leaf descendant

    Args:
        doc: Waste Calculator document (frappe._dict)
        service_config: Service Configuration document

    Raises:
        frappe.ValidationError: If group waste type has no leaf selections
    """
    # Get waste_types from service configuration
    config_result = get_service_configuration(
        doc.isic_classification, doc.service_type)
    waste_distributions = config_result.get('waste_distributions', [])

    if not waste_distributions:
        return

    # New model (desk Waste Calculator): each `wastes` row mirrors a configuration
    # distribution and carries the selected leaf waste items in `waste_item`.
    # Require a selection per row and skip the legacy leaf auto-population.
    wastes = doc.get('wastes') or []
    if any(_row_value(w, 'waste_item') for w in wastes):
        for w in wastes:
            if not (_row_value(w, 'waste_item') or '').strip():
                waste_type = _row_value(w, 'waste_type')
                label = frappe.db.get_value(
                    'Waste Type', waste_type, 'waste_name') or waste_type
                frappe.throw(
                    _("Please select at least one Waste Item for '{0}'.").format(
                        frappe.bold(label)),
                    title=_("Waste Item Required")
                )
        return

    # Get current wastes selected by user
    current_wastes = {
        waste.get('waste_type') if isinstance(
            waste, dict) else getattr(waste, 'waste_type', None)
        for waste in doc.get('wastes', [])
    }
    current_wastes.discard(None)  # Remove None values

    # Track leaf wastes to auto-add
    wastes_to_add = []

    # Validate each waste_type from waste_distributions
    for waste_dist in waste_distributions:
        waste_type = waste_dist.get('waste_type') if isinstance(
            waste_dist, dict) else waste_dist.waste_type
        is_group = waste_dist.get('is_group') if isinstance(
            waste_dist, dict) else waste_dist.is_group

        if not waste_type:
            continue

        if not is_group:
            # Leaf waste type - auto-add if not already selected
            if waste_type not in current_wastes:
                wastes_to_add.append(waste_type)
                current_wastes.add(waste_type)
        else:
            # Group waste type - validate user selected at least one leaf descendant
            leaf_descendants = get_leaf_descendants(waste_type)
            selected_descendants = current_wastes.intersection(
                set(leaf_descendants))

            if not selected_descendants:
                waste_type_label = frappe.db.get_value(
                    'Waste Type', waste_type, 'waste_name') or waste_type
                frappe.throw(
                    _("Please select at least one waste type from the '{0}' category in the Wastes field.").format(
                        frappe.bold(waste_type_label)
                    ),
                    title=_("Waste Selection Required")
                )

    # Auto-populate leaf wastes
    if wastes_to_add:
        if not doc.get('wastes'):
            doc.wastes = []

        for waste_type in wastes_to_add:
            if isinstance(doc.wastes, list):
                doc.wastes.append({'waste_type': waste_type})
            else:
                doc.append('wastes', {'waste_type': waste_type})


def validate_whole_number(value, must_be_whole, field_label):
    """
    Validate that a value is a whole number if required

    Args:
        value (float): The value to validate
        must_be_whole (bool): Whether the value must be a whole number
        field_label (str): Label for the field (for error message)

    Raises:
        frappe.ValidationError: If value is not a whole number when required
    """
    if must_be_whole and value and value % 1 != 0:
        frappe.throw(
            _("The {0} must be a whole number. Please enter a value without decimals.").format(
                frappe.bold(field_label)
            ),
            title=_("Invalid Value")
        )


def calculate_facility_measurement(doc):
    """
    Calculate total facility measurement
    Handles both simple and composite UOM measurements

    For composite UOMs: Multiplies all UOM values from child table
    For simple UOMs: Returns facility_measurement field directly

    Args:
            doc: Waste Calculator document

    Returns:
            float: Total facility measurement
    """
    if doc.is_composite_uom and doc.get('facility_measurements'):
        # For composite UOM, validate and multiply all UOM values
        total = 1
        for row in doc.facility_measurements:
            if isinstance(row, dict):
                uom_value = row.get('uom_value', 0)
                must_be_whole = row.get('must_be_whole_number', 0)
                uom = row.get('uom', 'UOM')
            else:
                uom_value = row.uom_value or 0
                must_be_whole = row.must_be_whole_number or 0
                uom = row.uom or 'UOM'

            # Validate whole number requirement for composite measurements
            validate_whole_number(uom_value, must_be_whole, uom)
            total *= uom_value
        return total
    else:
        # Validate whole number requirement for simple measurement
        validate_whole_number(
            doc.facility_measurement,
            doc.get('must_be_whole_number', 0),
            'Facility Measurement'
        )
        return doc.facility_measurement or 0


def calculate_by_cluster_classification(service_config, facility_measurement, doc):
    """
    Calculate waste using Cluster Classification method
    Determines which threshold cluster the facility falls into

    Args:
            service_config: Service Configuration document
            facility_measurement: Facility measurement value
            doc: Waste Calculator document

    Returns:
            dict: Calculation results with waste and generation rate
    """
    # Get generation classifications (threshold clusters), then select from them.
    clusters = frappe.get_all(
        'Waste Generation Classification',
        filters={'parent': service_config.name},
        fields=['max_threshold', 'total_converted_volume',
                'container_type', 'count'],
        order_by='max_threshold asc'
    )
    return select_cluster_waste(service_config, facility_measurement, clusters)


def select_cluster_waste(service_config, facility_measurement, clusters):
    """Cluster-classification calculation over pre-fetched clusters (DB-free).

    Shared by the Waste Calculator (which fetches per config) and the Service
    Configuration page (which bulk-fetches once). ``clusters`` must be ordered by
    ``max_threshold`` ascending; each item needs max_threshold, total_converted_volume,
    container_type and count.
    """
    if not clusters:
        # No clusters defined, use direct generation rate
        return calculate_by_generation_rate(service_config, facility_measurement, None)

    # Determine which cluster the facility falls into
    selected_volume = None
    selected_threshold = None
    selected_container = None
    selected_count = None

    for cluster in clusters:
        if facility_measurement <= cluster.max_threshold:
            selected_volume = cluster.total_converted_volume
            selected_threshold = cluster.max_threshold
            selected_container = cluster.container_type
            selected_count = cluster.count
            break

    # If facility exceeds all thresholds, use mean/median based on config
    if selected_volume is None:
        if service_config.calculate_generation_rate_by == 'Median':
            generation_rate = service_config.median_generation_rate or 0
        else:
            generation_rate = service_config.mean_generation_rate or 0

        facility_waste = facility_measurement * generation_rate

        return {
            'facility_waste': facility_waste,
            'generation_rate': generation_rate,
            'method': 'Cluster Classification (Exceeded - Using {0})'.format(
                service_config.calculate_generation_rate_by
            )
        }

    # Use the cluster's pre-calculated converted volume directly
    # The total_converted_volume has already been converted to default volume unit
    facility_waste = selected_volume

    # Calculate generation rate for display purposes
    if facility_measurement and facility_measurement > 0:
        generation_rate = facility_waste / facility_measurement
    else:
        generation_rate = 0

    return {
        'facility_waste': facility_waste,
        'generation_rate': generation_rate,
        'method': 'Cluster Classification',
        'selected_threshold': selected_threshold,
        'selected_volume': selected_volume,
        'container_type': selected_container,
        'container_count': selected_count
    }


def calculate_by_generation_rate(service_config, facility_measurement, doc):
    """
    Calculate waste using Generation Rate method
    Direct multiplication of measurement by generation rate

    Args:
            service_config: Service Configuration document
            facility_measurement: Facility measurement value
            doc: Waste Calculator document

    Returns:
            dict: Calculation results with waste and generation rate
    """
    # Use mean or median based on configuration
    if service_config.calculate_generation_rate_by == 'Median':
        generation_rate = service_config.median_generation_rate or 0
    else:
        generation_rate = service_config.mean_generation_rate or 0

    facility_waste = facility_measurement * generation_rate

    return {
        'facility_waste': facility_waste,
        'generation_rate': generation_rate,
        'method': 'Generation Rate ({0})'.format(
            service_config.calculate_generation_rate_by
        )
    }


# Tolerance for matching Rating fractions (a half-star is 0.1 of the 0-1 range, so
# 0.001 cleanly distinguishes adjacent whole- and half-star values while absorbing
# any floating-point noise).
RATING_MATCH_TOLERANCE = 0.001


def get_rating_safety_factor(service_config_name, facility_rating):
    """
    Get the safety-factor multiplier for a facility rating from the Rating Classification
    child table.

    The safety factor is a multiplier applied to the generated waste (mirroring the
    Regional Service Configuration's safety factor), so an unmatched rating returns the
    neutral multiplier 1 (no effect) rather than 0.

    Frappe's Rating fieldtype stores a fraction of the max (e.g. 2 of 5 stars -> 0.4),
    so both the configured thresholds and the supplied facility rating arrive as
    fractions. They are matched with a small tolerance, which supports whole- and
    fractional-star ratings alike (the UI enforces whole stars when fractional ratings
    are disabled in Service Settings).

    Args:
            service_config_name: Service Configuration name
            facility_rating: Facility rating as a Rating fraction (0-1)

    Returns:
            float: Safety-factor multiplier (1 = no effect)
    """
    target = flt(facility_rating)
    if not target:
        return 1

    rating_rows = frappe.get_all(
        'Rating Classification',
        filters={'parent': service_config_name},
        fields=['rating', 'safety_factor']
    )

    for row in rating_rows:
        if abs(flt(row.rating) - target) < RATING_MATCH_TOLERANCE:
            return flt(row.safety_factor) or 1

    return 1


def compute_waste_totals(config_doc, safety_multiplier, facility_measurement, doc,
                         rating_config_name=None, facility_rating=None):
    """Post-resolution waste math shared by the Waste Calculator and Service Quotation.

    The configuration is resolved by the caller — each obeys its own rules (the
    calculator is a sandbox; the quotation follows the Service Type priority engine) —
    so this owns only the arithmetic: the base waste and the rating + regional
    multipliers applied to it.

    The Facility Generated Waste is the base result, preserved before any multiplication;
    the Total Generated Waste applies both factors. Each factor defaults to 1 (no effect).

    Args:
        config_doc: the resolved compute configuration (a Service Configuration, or a
            Reconfiguration Regional Service Configuration).
        safety_multiplier: the regional (Safety-Factor RSC) multiplier; 1 otherwise.
        facility_measurement: the validated facility measurement.
        doc: the calculator / quotation document.
        rating_config_name: the configuration whose Rating Classification to read.
        facility_rating: the facility rating as a Rating fraction (0-1); falsy = no rating.

    Returns:
        frappe._dict: calc_result, generation_rate, facility_generated_waste,
        total_generated_waste, rating_safety_factor, regional_safety_factor.
    """
    if config_doc.calculate_facility_wastes_by == "Cluster Classification":
        calc_result = calculate_by_cluster_classification(config_doc, facility_measurement, doc)
    else:  # Generation Rate
        calc_result = calculate_by_generation_rate(config_doc, facility_measurement, doc)

    # Base facility waste — preserved as-is, before any safety-factor multiplication.
    facility_generated_waste = calc_result['facility_waste']

    # Rating safety factor: a multiplier from the chosen configuration's Rating
    # Classification. Defaults to 1 (no effect) when there is no rating or no match.
    rating_safety_factor = 1
    if facility_rating:
        rating_safety_factor = get_rating_safety_factor(rating_config_name, facility_rating)

    # Regional safety factor: a Safety-Factor RSC multiplier (1 when not applicable).
    regional_safety_factor = safety_multiplier

    # Total waste applies the rating and regional multipliers to the base.
    total_generated_waste = facility_generated_waste * rating_safety_factor * regional_safety_factor

    return frappe._dict({
        'calc_result': calc_result,
        'generation_rate': calc_result.get('generation_rate', 0),
        'facility_generated_waste': facility_generated_waste,
        'total_generated_waste': total_generated_waste,
        'rating_safety_factor': rating_safety_factor,
        'regional_safety_factor': regional_safety_factor,
    })


def suggest_container(total_waste, waste_volume_unit, service_config_name):
    """
    Suggest container from Service Configuration's generation_classification table
    Matches waste against pre-defined threshold classifications

    NOTE: For services with recurring waste, classifications are on DAILY basis.

    Args:
        total_waste: Total waste volume (in waste_volume_unit)
        waste_volume_unit: UOM of the waste volume (from Service Configuration)
        service_config_name: Service Configuration name

    Returns:
        dict: Container name and count from generation_classification
    """
    if not total_waste or not waste_volume_unit or not service_config_name:
        return {'container': None, 'count': 0}

    # Get generation classifications from Service Configuration, then pick from them.
    classifications = frappe.get_all(
        'Waste Generation Classification',
        filters={'parent': service_config_name},
        fields=['container_type', 'count', 'total_converted_volume'],
        order_by='total_converted_volume asc'
    )
    return pick_container(classifications, total_waste)


def pick_container(classifications, total_waste):
    """Pick a suggested container over pre-fetched classifications (DB-free).

    Shared by the Waste Calculator (per config) and the Service Configuration page
    (bulk-fetched once). ``classifications`` must be ordered by total_converted_volume
    ascending; each needs container_type, count and total_converted_volume.

    Returns the smallest classification whose capacity covers the waste; if the waste
    exceeds every classification, scales the largest container's count proportionally.
    """
    if not total_waste or not classifications:
        return {'container': None, 'count': 0}

    # Find the smallest classification that can handle the waste
    # (total_converted_volume is already in the default volume unit).
    for classification in classifications:
        if classification.total_converted_volume >= total_waste:
            return {
                'container': classification.container_type,
                'count': classification.count
            }

    # Waste exceeds all classifications → scale the largest container count up.
    largest = classifications[-1]
    if largest.total_converted_volume > 0:
        import math
        scale_factor = total_waste / largest.total_converted_volume
        count_needed = math.ceil(largest.count * scale_factor)
        return {
            'container': largest.container_type,
            'count': count_needed
        }

    return {'container': None, 'count': 0}


# ============================================================================
# SUGGESTED-CONTAINER ROW BUILDERS  (shared by Service Quotation Container and
# Waste Calculator's generated_wastes / WC Waste Container)
# ============================================================================

def build_container_geometry_row(container_type, count, default_volume_unit):
    """Build a container row's geometry + volume-conversion fields, mirroring the
    logic of Waste Generation Classification. `suggested_container_type` is included
    for the Service Quotation table and harmlessly ignored where it doesn't exist."""
    ct = frappe.db.get_value(
        "Container Type",
        container_type,
        ["volume", "volume_unit", "tare_weight", "weight_unit", "image"],
        as_dict=True,
    ) or frappe._dict()

    count = cint(count)
    volume = flt(ct.volume)
    total_volume = volume * count

    if ct.volume_unit and default_volume_unit and ct.volume_unit == default_volume_unit:
        conversion_factor = 1.0
    elif ct.volume_unit and default_volume_unit:
        try:
            conversion_factor = get_volume_conversion_factor(
                ct.volume_unit, default_volume_unit)
        except Exception:
            conversion_factor = 0.0
    else:
        conversion_factor = 0.0

    tare_weight = flt(ct.tare_weight)
    return {
        "container_type": container_type,
        "suggested_container_type": container_type,
        "container_count": count,
        "volume": volume,
        "volume_unit": ct.volume_unit,
        "total_volume": total_volume,
        "default_volume_unit": default_volume_unit,
        "conversion_factor": conversion_factor,
        "converted_volume": volume * conversion_factor,
        "total_converted_volume": total_volume * conversion_factor,
        "tare_weight": tare_weight,
        "weight_unit": ct.weight_unit,
        "total_tare_weight": tare_weight * count,
        "image": ct.image,
    }


def resolve_calculation_config(calculation_based_on, config_name):
    """Return ``(config_doc_to_compute_from, safety_factor_multiplier)`` for a chosen
    configuration. A Reconfiguration RSC is standalone (multiplier 1); a Safety-Factor
    RSC defers to its base Service Configuration and carries the safety factor as the
    multiplier. Shared by Service Quotation and the Waste Calculator."""
    if calculation_based_on == "Regional Service Configuration":
        rsc = frappe.get_doc("Regional Service Configuration", config_name)
        if rsc.configuration_method == "Safety Factor":
            base_sc = frappe.get_doc(
                "Service Configuration", rsc.service_configuration)
            return base_sc, flt(rsc.safety_factor) or 1
        return rsc, 1
    return frappe.get_doc("Service Configuration", config_name), 1


def single_waste_type(service_type):
    """The Waste Type for a single-waste service; None when the service has
    multiple waste types (a single container can't represent multiple waste types)."""
    if not service_type:
        return None
    wastes = frappe.get_all(
        "Service Waste Type",
        filters={"parent": service_type, "parenttype": "Service Type"},
        fields=["waste_type"],
    )
    if len(wastes) == 1:
        return wastes[0].waste_type
    return None


def build_generated_container_rows(
        config_doc, default_volume_unit, total_generated_waste, facility_generated_waste,
        generation_rate, regional_safety_factor, rating_safety_factor,
        service_type=None, single_suggestion=None, allocate_override=None
):
    """Build the suggested container rows shared by Service Quotation Container and
    the Waste Calculator's generated_wastes.

    When allocation is on (the config's ``allocate_container_for_each_waste_type`` or
    an explicit ``allocate_override``) and a ``waste_distributions`` table exists, emit
    one row per waste type sized to its share; otherwise a single row for the whole
    facility waste.
    """
    shared = {
        "generated_rate_per_unit": generation_rate,
        "regional_safety_factor": regional_safety_factor,
        "rating_safety_factor": rating_safety_factor,
    }

    # Waste distributions and the per-type allocation flag are owned by the base
    # Service Configuration (an RSC defers to it); container sizing below still uses
    # the compute config's own generation classification (config_doc).
    dist_config = waste_source_config(config_doc)
    distributions = dist_config.get("waste_distributions") or []
    allocate = dist_config.get(
        "allocate_container_for_each_waste_type") if allocate_override is None else allocate_override
    rows = []

    if allocate and distributions:
        for dist in distributions:
            share = flt(dist.distribution_percentage) / 100.0
            type_waste = total_generated_waste * share
            suggestion = suggest_container(
                type_waste, default_volume_unit, config_doc.name)
            if not suggestion.get("container"):
                continue
            row = build_container_geometry_row(
                suggestion["container"], suggestion["count"], default_volume_unit)
            row.update(shared)
            row.update({
                "waste_type": dist.waste_type,
                "waste_type_percentage": dist.distribution_percentage,
                "facility_generated_waste": facility_generated_waste * share,
                "total_generated_waste": type_waste,
            })
            rows.append(row)
    else:
        suggestion = single_suggestion or suggest_container(
            total_generated_waste, default_volume_unit, config_doc.name
        )
        if suggestion.get("container"):
            row = build_container_geometry_row(
                suggestion["container"], suggestion["count"], default_volume_unit)
            row.update(shared)
            row.update({
                "waste_type": single_waste_type(service_type),
                "waste_type_percentage": 100,
                "facility_generated_waste": facility_generated_waste,
                "total_generated_waste": total_generated_waste,
            })
            rows.append(row)

    return rows


def build_calculation_details(
        facility_measurement,
        calc_result,
        rating_safety_factor,
        regional_safety_factor,
        facility_generated_waste,
        total_generated_waste,
        service_config,
        doc,
        apply_service_duration,
        generated_wastes=None
):
    """
    Build detailed HTML calculation breakdown for display

    Args:
            facility_measurement: Facility measurement value
            calc_result: Calculation result dict from cluster/generation rate method
            rating_safety_factor: Rating safety-factor multiplier (1 = no effect)
            regional_safety_factor: Regional safety-factor multiplier (1 = no effect)
            facility_generated_waste: Calculated facility waste
            total_generated_waste: Total combined waste
            service_config: Service Configuration document
            doc: Waste Calculator document
            apply_service_duration: Whether the service type applies service duration

    Returns:
            str: HTML formatted calculation details
    """
    generation_rate = calc_result.get('generation_rate', 0)
    method = calc_result.get('method', 'Unknown')

    # Get default units from Naqel Settings
    default_units = frappe.get_cached_doc('Naqel Settings')
    default_volume_unit = default_units.default_volume_unit
    default_mass_unit = default_units.default_mass_unit
    default_density_unit = default_units.default_density_unit

    # Build waste distributions section and get total weight
    waste_distributions_section, total_daily_weight = build_waste_distributions_section(
        service_config, doc, total_generated_waste, default_volume_unit, default_mass_unit)

    # Calculate time-based projections if recurring waste
    weekly_waste = total_generated_waste * 7 if apply_service_duration else 0
    monthly_waste = total_generated_waste * 30 if apply_service_duration else 0
    yearly_waste = total_generated_waste * 365 if apply_service_duration else 0

    # Calculate weight projections if recurring waste and weight is available
    weekly_weight = total_daily_weight * \
        7 if apply_service_duration and total_daily_weight else 0
    monthly_weight = total_daily_weight * \
        30 if apply_service_duration and total_daily_weight else 0
    yearly_weight = total_daily_weight * \
        365 if apply_service_duration and total_daily_weight else 0

    # Prepare context for template
    context = {
        'facility_measurement': facility_measurement,
        'generation_rate': generation_rate,
        'method': method,
        'calc_result': calc_result,
        'rating_safety_factor': rating_safety_factor,
        'regional_safety_factor': regional_safety_factor,
        'facility_generated_waste': facility_generated_waste,
        'total_generated_waste': total_generated_waste,
        'default_volume_unit': default_volume_unit,
        'default_mass_unit': default_mass_unit,
        'default_density_unit': default_density_unit,
        'service_config': service_config,
        'apply_service_duration': apply_service_duration,
        'weekly_waste': weekly_waste,
        'monthly_waste': monthly_waste,
        'yearly_waste': yearly_waste,
        'total_daily_weight': total_daily_weight,
        'weekly_weight': weekly_weight,
        'monthly_weight': monthly_weight,
        'yearly_weight': yearly_weight,
        'waste_distributions_section': waste_distributions_section,
        'generated_wastes': generated_wastes or []
    }

    # Render template based on caller doctype
    if getattr(doc, 'doctype', '') == 'Service Request':
        template_path = 'naqel/nq_setup/doctype/waste_calculator/service_request_waste_report.html'
    else:
        template_path = 'naqel/nq_setup/doctype/waste_calculator/waste_calculation_report.html'
    return frappe.render_template(template_path, context)


def build_waste_distributions_section(service_config, doc, total_generated_waste, default_volume_unit, default_mass_unit):
    """
    Build HTML section for waste type distributions and selected waste types

    Args:
        service_config: Service Configuration document
        doc: Waste Calculator document
        total_generated_waste: Total generated waste volume
        default_volume_unit: Default unit for volume
        default_mass_unit: Default unit for mass

    Returns:
        tuple: (HTML formatted waste distributions section, total daily weight)
    """
    # Waste distributions are owned by the base Service Configuration; a Regional
    # Service Configuration defers to it (the source of truth for waste types).
    dist_config = waste_source_config(service_config)
    waste_distributions_raw = frappe.get_all(
        'Waste Distribution',
        filters={'parent': dist_config.name},
        fields=['waste_type', 'is_group', 'distribution_percentage'],
        order_by='idx'
    )

    if not waste_distributions_raw:
        return ""

    # Get waste type details
    waste_type_names = [wd.waste_type for wd in waste_distributions_raw]
    waste_details = {}

    if waste_type_names:
        waste_type_data = frappe.get_all(
            'Waste Type',
            filters={'name': ['in', waste_type_names]},
            fields=['name', 'waste_name', 'waste_standard_density',
                    'waste_density_unit', 'description', 'is_group']
        )
        waste_details = {wt.name: wt for wt in waste_type_data}

    # Prepare waste distributions with enriched data including weight calculations
    waste_distributions = []
    for idx, wd in enumerate(waste_distributions_raw):
        wt_data = waste_details.get(wd.waste_type, {})
        waste_name = _(wt_data.get('waste_name', wd.waste_type))
        is_group = wt_data.get('is_group', wd.is_group)
        density = wt_data.get('waste_standard_density', 0)
        density_unit = _(wt_data.get('waste_density_unit', '')
                         ) if wt_data.get('waste_density_unit') else ''
        description = _(wt_data.get('description', '')
                        ) if wt_data.get('description') else ''

        density_text = f"{density:.2f} {density_unit}" if density and density_unit else _(
            "Not Specified")

        # Calculate volume for this waste type based on distribution percentage
        waste_volume = (total_generated_waste *
                        wd.distribution_percentage) / 100

        # Calculate weight if density is available and greater than 0
        weight_value = None
        weight_text = _("N/A")
        if density and density > 0:
            weight_value = waste_volume * density
            weight_text = f"{weight_value:.2f} {_(default_mass_unit)}"

        waste_distributions.append({
            'waste_name': waste_name,
            'is_group': is_group,
            'distribution_percentage': wd.distribution_percentage,
            'density_text': density_text,
            'waste_volume': waste_volume,
            'waste_volume_text': f"{waste_volume:.2f} {_(default_volume_unit)}",
            'weight_value': weight_value,
            'weight_text': weight_text,
            'description': description
        })

    # Get selected waste types from doc. New model: leaf items live in each row's
    # `waste_item` (comma-joined); legacy portal payload: each row is a leaf
    # `waste_type`. Support both, de-duplicating while preserving order.
    selected_wastes_list = []
    if doc.get('wastes'):
        selected_waste_names = []
        for w in doc.wastes:
            items = parse_waste_items(_row_value(w, 'waste_item'))
            if not items:
                waste_type = _row_value(w, 'waste_type')
                items = [waste_type] if waste_type else []
            selected_waste_names.extend(items)
        selected_waste_names = list(dict.fromkeys(selected_waste_names))

        if selected_waste_names:
            selected_waste_data = frappe.get_all(
                'Waste Type',
                filters={'name': ['in', selected_waste_names]},
                fields=['name', 'waste_name', 'waste_standard_density',
                        'waste_density_unit', 'description']
            )

            for idx, waste_data in enumerate(selected_waste_data):
                waste_label = _(waste_data.get('waste_name', waste_data.name))
                density = waste_data.get('waste_standard_density', 0)
                density_unit = _(waste_data.get('waste_density_unit', '')) if waste_data.get(
                    'waste_density_unit') else ''
                description = _(waste_data.get('description', '')
                                ) if waste_data.get('description') else ''

                density_text = f"{density:.2f} {density_unit}" if density and density_unit else _(
                    "Not Specified")

                selected_wastes_list.append({
                    'waste_label': waste_label,
                    'density_text': density_text,
                    'description': description
                })

    # Calculate total daily weight by summing all waste weights
    total_daily_weight = sum(
        wd['weight_value'] for wd in waste_distributions if wd['weight_value'] is not None
    )

    # Prepare context for template render
    context = {
        'waste_distributions': enumerate(waste_distributions),
        'selected_wastes': enumerate(selected_wastes_list) if selected_wastes_list else None
    }

    # Render template based on caller doctype
    if getattr(doc, 'doctype', '') == 'Service Request':
        template_path = 'naqel/nq_setup/doctype/waste_calculator/service_request_waste_distributions.html'
    else:
        template_path = 'naqel/nq_setup/doctype/waste_calculator/waste_distributions_section.html'
    return frappe.render_template(template_path, context), total_daily_weight


# ============================================================================
# CONFIGURATION & UTILITY METHODS
# These methods provide shared functionality for waste calculations
# ============================================================================

@frappe.whitelist()
def get_service_type_details(service_type):
    """
    Fetch service type details to populate in Service Order or Waste Calculator

    Args:
        service_type (str): Name of the Service Type

    Returns:
        dict: Service type fields (service_license)
    """
    if not service_type:
        return {}

    service_details = frappe.db.get_value(
        'Service Type',
        service_type,
        ['grants_license'],
        as_dict=1
    )

    if not service_details:
        frappe.throw(_("Service Type '{0}' not found").format(service_type))

    return {
        'service_license': service_details.grants_license or 0
    }


@frappe.whitelist()
def get_facility_uom_details(facility_uom):
    """
    Fetch facility UOM details to populate in Waste Calculator

    Args:
        facility_uom (str): Name of the Facility UOM

    Returns:
        dict: Facility UOM fields (must_be_whole_number, is_composite_uom)
    """
    if not facility_uom:
        return {}

    uom_details = frappe.db.get_value(
        'Facility UOM',
        facility_uom,
        ['must_be_whole_number', 'is_composite_uom'],
        as_dict=1
    )

    if not uom_details:
        frappe.throw(_("Facility UOM '{0}' not found").format(facility_uom))

    return {
        'must_be_whole_number': uom_details.must_be_whole_number or 0,
        'is_composite_uom': uom_details.is_composite_uom or 0
    }


@frappe.whitelist()
def get_service_configuration(isic_classification, service_type):
    """
    Get waste distributions from Service Configuration

    Priority order:
    1. Check for General Configuration (is_general_configuration=1) for the service type
    2. If not found, traverse ISIC Classification hierarchy to find specific configuration

    Args:
        isic_classification (str): ISIC Classification name
        service_type (str): Service Type name

    Returns:
        dict: {
            'waste_distributions': list - Waste types with distribution percentages,
            'service_configuration': str - Service Configuration name
        }
    """
    if not isic_classification or not service_type:
        return {'waste_distributions': [], 'service_configuration': None}

    # STEP 1: Check for General Configuration first (highest priority)
    general_config = frappe.db.get_value(
        'Service Configuration',
        {
            'disabled': 0,
            'is_general_configuration': 1,
            'service_type': service_type
        },
        ['name', 'title', 'allocate_container_for_each_waste_type'],
        as_dict=1
    )

    def _enrich_distributions(distributions):
        """Attach translated waste_name to each distribution row."""
        if not distributions:
            return distributions
        wt_names = [d.waste_type for d in distributions]
        wt_map = {
            wt['name']: wt['waste_name']
            for wt in frappe.get_all(
                'Waste Type',
                filters={'name': ['in', wt_names]},
                fields=['name', 'waste_name']
            )
        }
        for dist in distributions:
            dist['waste_name'] = _(wt_map.get(
                dist['waste_type'], dist['waste_type']))
        return distributions

    if general_config:
        # General configuration found - get waste distributions
        waste_distributions = frappe.get_all(
            'Waste Distribution',
            filters={'parent': general_config.name},
            fields=[
                'waste_type',
                'is_group',
                'distribution_percentage',
                'default_waste_item'
            ],
            order_by='idx'
        )

        return {
            'waste_distributions': _enrich_distributions(waste_distributions),
            'service_configuration': general_config.name,
            'allocate_container_for_each_waste_type': general_config.allocate_container_for_each_waste_type or 0
        }

    # STEP 2: No general configuration found - traverse ISIC hierarchy
    # fetch_all=False: lazy parent_category walk, short-circuits on first match
    for current_isic in get_isic_ancestors(isic_classification, fetch_all=False):
        config = frappe.db.get_value(
            'Service Configuration',
            {'disabled': 0, 'isic_classification': current_isic,
                'service_type': service_type},
            ['name', 'title', 'allocate_container_for_each_waste_type'],
            as_dict=1
        )

        if config:
            waste_distributions = frappe.get_all(
                'Waste Distribution',
                filters={'parent': config.name},
                fields=['waste_type', 'is_group',
                        'distribution_percentage', 'default_waste_item'],
                order_by='idx'
            )
            return {
                'waste_distributions': _enrich_distributions(waste_distributions),
                'service_configuration': config.name,
                'allocate_container_for_each_waste_type': config.allocate_container_for_each_waste_type or 0
            }

    # No configuration found in entire hierarchy
    message = _(
        "No Service Configuration found for ISIC Classification '{0}' with Service Type '{1}'. "
        "Please create a Service Configuration for this ISIC Classification or one of its parent levels."
    ).format(
        frappe.bold(isic_classification),
        frappe.bold(service_type)
    )

    frappe.throw(message, title=_("Service Configuration Not Found"))


def resolve_uom_config_doc(config_name):
    """Resolve the Service Configuration that owns the Facility UOM / conversions and
    the waste distributions (waste types + default waste items).

    A Service Configuration is used directly. A Regional Service Configuration carries
    neither — the base Service Configuration it references is the single source of
    truth — so any RSC (Safety-Factor or Reconfiguration) resolves to its base SC.
    """
    if not config_name:
        return None
    if frappe.db.exists("Service Configuration", config_name):
        return frappe.get_doc("Service Configuration", config_name)
    base_sc = frappe.db.get_value(
        "Regional Service Configuration", config_name, "service_configuration")
    if base_sc:
        return frappe.get_doc("Service Configuration", base_sc)
    return None


def waste_source_config(config_doc):
    """The configuration that owns the waste distributions (waste types, percentages,
    default waste items). A Reconfiguration RSC computes from itself but holds no
    distributions, so it defers to its base SC — the source of truth, exactly like
    Facility UOMs. A Service Configuration (incl. the SC a Safety-Factor RSC already
    resolves to) is returned as-is.
    """
    if getattr(config_doc, "doctype", None) == "Regional Service Configuration":
        return resolve_uom_config_doc(config_doc.name) or config_doc
    return config_doc


@frappe.whitelist()
def get_allowed_facility_uoms(service_configuration):
    """Allowed Facility UOMs for the chosen configuration: its default facility_uom
    plus every subsidiary UOM in the conversions table. The first entry is the default.

    Resolves a Regional Service Configuration to the config it actually computes from,
    so the UOM list (and the auto-populated default) stays consistent with the waste
    calculation.

    Args:
        service_configuration (str): Service Configuration or Regional Service
            Configuration name

    Returns:
        list: Allowed Facility UOM names (default first)
    """
    config_doc = resolve_uom_config_doc(service_configuration)
    if not config_doc or not config_doc.facility_uom:
        return []

    allowed_uoms = [config_doc.facility_uom]
    allowed_uoms.extend(
        row.subsidiary_uom for row in (config_doc.get("uoms") or []) if row.subsidiary_uom
    )
    return allowed_uoms


@frappe.whitelist()
def get_uom_conversion_factor(service_configuration, facility_uom):
    """Return the conversion factor for a facility UOM relative to the config's default.

    Returns 1 if it's the default UOM, the stored factor from the uoms table if
    it's a subsidiary, or 0 if not found.
    """
    config_doc = resolve_uom_config_doc(service_configuration)
    if not config_doc:
        return 1

    if facility_uom == config_doc.facility_uom:
        return 1

    for row in config_doc.get("uoms") or []:
        if row.subsidiary_uom == facility_uom:
            return frappe.utils.flt(row.conversion_factor) or 1

    return 1


@frappe.whitelist()
def get_facility_uom_hierarchy(facility_uom):
    """
    Recursively get all subsidiary UOMs from a composite Facility UOM
    Returns a list of UOMs in hierarchy order (main UOM first, then subsidiaries)

    Args:
        facility_uom (str): Facility UOM name

    Returns:
        list: List of dicts with UOM details (name, must_be_whole_number)
    """
    if not facility_uom:
        return []

    uom_hierarchy = []
    current_uom = facility_uom
    processed_uoms = set()  # Prevent infinite loops

    while current_uom and current_uom not in processed_uoms:
        processed_uoms.add(current_uom)

        # Get UOM details
        uom_data = frappe.db.get_value(
            'Facility UOM',
            current_uom,
            ['name', 'must_be_whole_number', 'is_composite_uom', 'subsidiary_uom'],
            as_dict=1
        )

        if not uom_data:
            break

        uom_hierarchy.append({
            'uom': uom_data.name,
            'must_be_whole_number': uom_data.must_be_whole_number or 0,
            'is_composite_uom': uom_data.is_composite_uom or 0
        })

        # Check if this UOM has a subsidiary
        if uom_data.is_composite_uom and uom_data.subsidiary_uom:
            current_uom = uom_data.subsidiary_uom
        else:
            break

    return uom_hierarchy


@frappe.whitelist()
def get_allowed_waste_types(waste_types):
    """
    Get all leaf waste types (is_group=0) that are descendants of the waste_types

    Uses shared get_leaf_descendants helper for DRY code

    Args:
        waste_types (str): JSON string of waste_type names from waste_types child table

    Returns:
        list: List of allowed leaf Waste Type objects with full details
    """
    if not waste_types:
        return []

    # Parse waste_types if it's a JSON string
    if isinstance(waste_types, str):
        try:
            waste_types = json.loads(waste_types)
        except:
            return []

    if not isinstance(waste_types, list):
        return []

    allowed_waste_types = set()

    for waste_type in waste_types:
        # Extract waste_type name
        waste_name = waste_type.get('waste_type') if isinstance(
            waste_type, dict) else waste_type

        if not waste_name:
            continue

        # Get leaf descendants using shared helper
        leaf_descendants = get_leaf_descendants(waste_name)
        allowed_waste_types.update(leaf_descendants)

    # Fetch full waste type objects with all fields
    if not allowed_waste_types:
        return []

    waste_type_objects = frappe.get_all(
        'Waste Type',
        filters={'name': ['in', list(allowed_waste_types)]},
        fields=['name', 'waste_name', 'is_group', 'waste_standard_density',
                'waste_density_unit', 'description'],
        order_by='waste_name asc'
    )

    for item in waste_type_objects:
        item['waste_name'] = _(item.get('waste_name') or item['name'])

    return waste_type_objects
