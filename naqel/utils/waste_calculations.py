# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

"""
Waste Generation Calculation Utilities

This module provides reusable calculation functions for waste generation statistics
and volume conversions used across Service Configuration and Regional Service Configuration.
"""

import frappe
from frappe import _
from frappe.utils import flt
from statistics import mean, median


def calculate_child_table_volumes(doc, volume_unit_field="default_volume_unit"):
    """
    Calculate volumes in child table before parent statistics

    Args:
        doc: Document object with generation_classification child table
        volume_unit_field: Name of the field containing the volume unit (default: "default_volume_unit")
    """
    if not doc.generation_classification:
        return

    volume_unit = getattr(doc, volume_unit_field, None)

    for row in doc.generation_classification:
        # Calculate total volume
        if row.container_standard_volume and row.count:
            row.total_volume = row.container_standard_volume * row.count
        else:
            row.total_volume = 0.0

        # Calculate converted volumes
        if not volume_unit:
            row.conversion_factor = 0.0
            row.container_converted_volume = 0.0
            row.total_converted_volume = 0.0
            continue

        # If same unit, conversion factor is 1
        if row.container_volume_unit == volume_unit:
            row.conversion_factor = 1.0
            row.container_converted_volume = row.container_standard_volume or 0.0
            row.total_converted_volume = row.total_volume or 0.0
            continue

        # Get conversion factor
        if not row.container_volume_unit:
            row.conversion_factor = 0.0
            row.container_converted_volume = 0.0
            row.total_converted_volume = 0.0
            continue

        try:
            conversion_factor = get_volume_conversion_factor(
                row.container_volume_unit,
                volume_unit
            )
            row.conversion_factor = conversion_factor

            if row.container_standard_volume:
                row.container_converted_volume = row.container_standard_volume * conversion_factor
            else:
                row.container_converted_volume = 0.0

            if row.total_volume and conversion_factor:
                row.total_converted_volume = row.total_volume * conversion_factor
            else:
                row.total_converted_volume = 0.0
        except Exception:
            row.conversion_factor = 0.0
            row.container_converted_volume = 0.0
            row.total_converted_volume = 0.0


def get_volume_conversion_factor(from_uom, to_uom):
    """
    Get conversion factor from one UOM to another
    Note: All conversions in UOM Conversion Factor use Litre as the base unit

    Args:
        from_uom: Source UOM name
        to_uom: Target UOM name

    Returns:
        float: Conversion factor

    Raises:
        frappe.ValidationError: If no conversion factor found
    """
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
        return float(to_uom_factor) / float(from_uom_factor)

    frappe.throw(
        _("No conversion factor found between {0} and {1}.").format(
            from_uom, to_uom
        )
    )


def calculate_threshold_statistics(doc):
    """
    Calculate mean and median thresholds from generation classification

    Args:
        doc: Document object with generation_classification child table
             and mean_threshold, median_threshold fields
    """
    if not doc.generation_classification:
        doc.mean_threshold = 0.0
        doc.median_threshold = 0.0
        return

    # Extract max_threshold values, filtering out None or zero values
    thresholds = [
        row.max_threshold
        for row in doc.generation_classification
        if row.max_threshold and row.max_threshold > 0
    ]

    # Calculate threshold statistics if we have valid data
    if thresholds:
        doc.mean_threshold = mean(thresholds)
        doc.median_threshold = median(thresholds)
    else:
        doc.mean_threshold = 0.0
        doc.median_threshold = 0.0


def calculate_volume_statistics(doc, volume_field="total_volume"):
    """
    Calculate mean and median volumes from generation classification

    Args:
        doc: Document object with generation_classification child table
             and mean_volume, median_volume fields
        volume_field: Name of the volume field to use for calculations
                     (default: "total_volume", alternative: "total_converted_volume")
    """
    if not doc.generation_classification:
        doc.mean_volume = 0.0
        doc.median_volume = 0.0
        return

    # Extract volume values, filtering out None or zero values
    volumes = [
        getattr(row, volume_field, 0)
        for row in doc.generation_classification
        if getattr(row, volume_field, 0) and getattr(row, volume_field, 0) > 0
    ]

    # Calculate volume statistics if we have valid data
    if volumes:
        doc.mean_volume = mean(volumes)
        doc.median_volume = median(volumes)
    else:
        doc.mean_volume = 0.0
        doc.median_volume = 0.0


def calculate_generation_rates(doc):
    """
    Calculate mean and median generation rates (volume per unit threshold)
    Used by Service Configuration

    Args:
        doc: Document object with mean_threshold, median_threshold, mean_volume, median_volume,
             mean_generation_rate, and median_generation_rate fields
    """
    # Calculate mean generation rate: mean_volume / mean_threshold
    if doc.mean_threshold and doc.mean_threshold > 0:
        doc.mean_generation_rate = doc.mean_volume / doc.mean_threshold
    else:
        doc.mean_generation_rate = 0.0

    # Calculate median generation rate: median_volume / median_threshold
    if doc.median_threshold and doc.median_threshold > 0:
        doc.median_generation_rate = doc.median_volume / doc.median_threshold
    else:
        doc.median_generation_rate = 0.0


def get_isic_ancestors(isic_classification, fetch_all=False):
    """
    Return the ISIC Classification names from the given node up to the root.

    Two modes controlled by ``fetch_all``:

    ``fetch_all=False`` (default — lazy walk):
        Walks the ``parent_category`` chain one hop at a time and returns a list
        of names in leaf-to-root order.  Each iteration costs one DB call, but
        the result can be consumed lazily by the caller so it short-circuits as
        soon as a match is found.  Best for single-document resolution where the
        matching config is usually only a few levels up.

    ``fetch_all=True`` (NSM bulk fetch):
        Issues a single SQL query using the Nested Set Model ``lft``/``rgt``
        columns to retrieve *all* ancestors at once.  Best when you need the
        complete ancestor set upfront — e.g. to build a ``set_query`` filter
        for a Link field.

    Args:
        isic_classification (str): Name of the starting ISIC Classification node.
        fetch_all (bool): When True use the NSM single-query approach;
                          when False walk parent_category lazily.

    Returns:
        list[str]: Ancestor names starting from ``isic_classification`` itself,
                   ordered leaf → root.  Empty list if the node does not exist.
    """
    if not isic_classification:
        return []

    if fetch_all:
        # --- NSM approach: single query ----------------------------------------
        ISIC = frappe.qb.DocType("ISIC Classification")
        node = frappe.db.get_value(
            "ISIC Classification", isic_classification, ["lft", "rgt"], as_dict=True
        )
        if not node:
            return []
        rows = (
            frappe.qb.from_(ISIC)
            .select(ISIC.name)
            .where((ISIC.lft <= node.lft) & (ISIC.rgt >= node.rgt))
            .run(as_list=True)
        )
        return [r[0] for r in rows]

    else:
        # --- Lazy parent_category walk -----------------------------------------
        result = []
        current = isic_classification
        while current:
            result.append(current)
            current = frappe.db.get_value(
                "ISIC Classification", current, "parent_category"
            )
        return result


def calculate_unit_generation_rate(doc):
    """
    Calculate generation rates based on calculate_generation_rate_by selection
    Used by Regional Service Configuration

    Args:
        doc: Document object with calculate_generation_rate_by, mean_threshold, median_threshold,
             mean_volume, median_volume, mean_generation_rate, and median_generation_rate fields
    """
    if doc.calculate_generation_rate_by == "Mean":
        if doc.mean_threshold and doc.mean_threshold > 0:
            doc.mean_generation_rate = doc.mean_volume / doc.mean_threshold
        else:
            doc.mean_generation_rate = 0.0
        # Clear median rate when using Mean
        doc.median_generation_rate = 0.0
    elif doc.calculate_generation_rate_by == "Median":
        if doc.median_threshold and doc.median_threshold > 0:
            doc.median_generation_rate = doc.median_volume / doc.median_threshold
        else:
            doc.median_generation_rate = 0.0
        # Clear mean rate when using Median
        doc.mean_generation_rate = 0.0
    else:
        doc.mean_generation_rate = 0.0
        doc.median_generation_rate = 0.0


def sort_and_validate_ratings(doc, table_field="ratings", rating_field="rating"):
    """Order a Rating Classification table ascending by rating and enforce unique
    ratings. Shared by Service Configuration and Regional Service Configuration.

    Two rows with the same rating are logically invalid regardless of their safety
    factors, so a duplicate raises a ValidationError.
    """
    rows = doc.get(table_field)
    if not rows:
        return

    # Order ascending and renumber idx so the persisted order matches.
    rows.sort(key=lambda row: flt(row.get(rating_field)))
    for index, row in enumerate(rows, start=1):
        row.idx = index

    # After sorting, duplicates are adjacent — a single linear pass detects them.
    previous = None
    for row in rows:
        current = round(flt(row.get(rating_field)), 4)
        if current == previous:
            frappe.throw(
                _("Each rating can appear only once in the Ratings table."),
                title=_("Duplicate Rating"),
            )
        previous = current
