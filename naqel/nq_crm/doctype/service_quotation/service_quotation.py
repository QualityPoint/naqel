# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, flt, getdate, nowdate

from naqel.utils.party import (
    clear_milestone_fields,
    set_conversion_factor,
    set_customer_name,
    set_net_facility_measurement,
    validate_duration_fields,
    validate_facility_belongs_to_party,
)
from naqel.utils.waste_calculations import get_isic_ancestors

# Resolution strategies for combining the ISIC and Address Division hierarchies.
# Mirrors the options of Service Type.regional_resolution_method.
ADDRESS_FIRST = "Address-First (Regional Priority)"
ISIC_FIRST = "ISIC-First (Configuration Priority)"
MOST_SPECIFIC = "Most Specific Overall"


class ServiceQuotation(Document):
    def before_validate(self):
        clear_milestone_fields(self, duration_field="service_duration", clear_when_milestone=False)
        set_conversion_factor(self)
        set_net_facility_measurement(self)
        self.set_default_valid_till()
        self.set_waste_configuration()
        self.flag_container_overrides()
        self.calculate_totals()

    def set_default_valid_till(self):
        """Default Valid Till on new quotations (authoritative; covers API/import).

        Mirrors erpnext: transaction_date + "Default Quotation Validity Days"
        from Service Settings, falling back to +1 month when unset. Read via the
        server ORM so it bypasses the client read-permission check on the setting.
        """
        if self.valid_till or not self.is_new():
            return

        days = cint(frappe.db.get_single_value(
            "Service Settings", "default_valid_till"))
        base = getdate(self.transaction_date or nowdate())
        self.valid_till = add_days(base, days) if days else add_months(base, 1)

    def set_waste_configuration(self):
        """Resolve the waste configuration for this quotation.

        Auto mode (``ignore_default_configuration`` unchecked): the system picks the
        winning Service / Regional Service Configuration by priority and fills both
        ``calculation_based_on`` and ``service_configuration``.

        Manual mode (Sales Manager ticked ``ignore_default_configuration``): the user's
        own pick is kept; we only warn (non-blocking) when it deviates from the default.
        """
        if not self.service_type or not self.isic_classification:
            return

        if self.ignore_default_configuration:
            self._warn_if_manual_deviates()
            return

        based_on, config = resolve_waste_configuration(
            self.service_type, self.isic_classification, self.territory
        )
        if based_on:
            self.calculation_based_on = based_on
        if config:
            self.service_configuration = config

    def _warn_if_manual_deviates(self):
        """Non-blocking notice when a manual pick differs from the priority default."""
        if not self.service_configuration:
            return
        _based_on, default_config = resolve_waste_configuration(
            self.service_type, self.isic_classification, self.territory
        )
        if default_config and self.service_configuration != default_config:
            frappe.msgprint(
                _("Selected configuration {0} deviates from the recommended default {1}.").format(
                    frappe.bold(self.service_configuration), frappe.bold(
                        default_config)
                ),
                title=_("Manual Configuration Override"),
                indicator="orange",
            )

    def validate(self):
        set_customer_name(self, "quotation_to", "party_name")
        validate_facility_belongs_to_party(self, "quotation_to", "party_name")
        validate_duration_fields(self, required_when_not_milestone=False)
        self.validate_valid_till()
        self.validate_taxes()

    def calculate_totals(self):
        """Authoritative server-side recompute of container line amounts, document
        totals, taxes, and grand/rounded totals — in both the document and company
        currency. Mirrors the client calculation so API/import saves (and any tampering
        with client-set values) are reconciled on every save."""
        conversion_rate = flt(self.conversion_rate) or 1.0
        duration_factor = 1
        if self.mode_of_service == "Duration-Based" and flt(self.service_duration):
            duration_factor = flt(self.service_duration)

        total_count = 0
        total_volume = total_converted = 0.0
        net_total = base_net_total = 0.0
        for row in self.containers or []:
            count = cint(row.container_count)
            row.total_volume = flt(row.volume) * count
            row.total_converted_volume = flt(row.converted_volume) * count
            row.total_tare_weight = flt(row.tare_weight) * count
            row.amount = flt(row.container_price) * count * duration_factor
            row.base_default_container_price = flt(
                row.default_container_price) * conversion_rate
            row.base_container_price = flt(
                row.container_price) * conversion_rate
            row.base_amount = flt(row.amount) * conversion_rate

            total_count += count
            total_volume += flt(row.total_volume)
            total_converted += flt(row.total_converted_volume)
            net_total += flt(row.amount)
            base_net_total += flt(row.base_amount)

        self.total_container_count = total_count
        self.total_volume = total_volume
        self.total_converted_volume = total_converted
        self.total = self.net_total = net_total
        self.base_total = self.base_net_total = base_net_total

        # Taxes ride on top of the net total.
        running = net_total
        taxes = self.taxes or []
        for index, tax in enumerate(taxes):
            rate = flt(tax.rate)
            if tax.charge_type == "On Net Total":
                tax_amount = net_total * rate / 100
            elif tax.charge_type in ("On Previous Row Amount", "On Previous Row Total"):
                ref_index = (cint(tax.row_id) or index) - 1
                ref = taxes[ref_index] if 0 <= ref_index < index else None
                base = flt(ref.tax_amount) if tax.charge_type == "On Previous Row Amount" else flt(
                    ref.total) if ref else 0
                tax_amount = (base if ref else 0) * rate / 100
            elif tax.charge_type == "Actual":
                tax_amount = flt(tax.tax_amount)
            else:
                tax_amount = 0

            tax.tax_amount = tax_amount
            running += tax_amount
            tax.total = running
            tax.base_tax_amount = tax_amount * conversion_rate
            tax.base_total = running * conversion_rate

        total_taxes = running - net_total if net_total else 0.0
        self.total_taxes_and_charges = total_taxes
        self.base_total_taxes_and_charges = total_taxes * conversion_rate

        grand_total = net_total + total_taxes
        base_grand_total = base_net_total + total_taxes * conversion_rate
        self.grand_total = grand_total
        self.base_grand_total = base_grand_total

        rounded = grand_total if self.disable_rounded_total else round(
            grand_total)
        base_rounded = base_grand_total if self.disable_rounded_total else round(
            base_grand_total)
        self.rounding_adjustment = rounded - grand_total
        self.rounded_total = rounded
        self.base_rounding_adjustment = base_rounded - base_grand_total
        self.base_rounded_total = base_rounded

        self.set_total_in_words(rounded, base_rounded)

    def set_total_in_words(self, total, base_total):
        """Spell out the totals using the shared app helper (SAR/Halala formatting),
        the same one Service Contract uses — document currency for in_words, company
        currency for base_in_words."""
        from naqel.utils.utils import format_currency_in_words

        self.in_words = format_currency_in_words(
            total, self.currency) if self.currency else ""
        company_currency = (
            frappe.get_cached_value(
                "Company", self.company, "default_currency") if self.company else None
        )
        self.base_in_words = (
            format_currency_in_words(
                base_total, company_currency) if company_currency else ""
        )

    def validate_taxes(self):
        """Mirror ERPNext's tax-row guards: a percentage row needs a rate, an Actual row
        needs an amount, and an 'On Previous Row' reference must point to an earlier row."""
        for tax in self.taxes or []:
            if tax.charge_type in ("On Previous Row Amount", "On Previous Row Total"):
                row_id = cint(tax.row_id)
                if not row_id or row_id >= tax.idx:
                    frappe.throw(
                        _("Row #{0}: '{1}' must reference a tax row that comes before it.").format(
                            tax.idx, tax.charge_type
                        ),
                        title=_("Invalid Tax Reference"),
                    )

    def flag_container_overrides(self):
        """Non-blocking notice when a container was changed from the calculated suggestion."""
        changed = [
            row for row in (self.containers or [])
            if row.suggested_container_type and row.container_type != row.suggested_container_type
        ]
        if not changed:
            return

        details = "<br>".join(
            _("Row {0}: suggested {1}, using {2}").format(
                row.idx, frappe.bold(row.suggested_container_type), frappe.bold(
                    row.container_type)
            )
            for row in changed
        )
        frappe.msgprint(
            _("One or more containers differ from the calculated suggestion:<br>{0}").format(
                details),
            title=_("Container Override"),
            indicator="orange",
        )

    def on_submit(self):
        frappe.db.set_value("Service Quotation", self.name, "status", "Open")

    def on_cancel(self):
        frappe.db.set_value("Service Quotation", self.name,
                            "status", "Cancelled")

    def set_sales_order_status(self):
        """Recompute status from the Sales Orders raised against this quotation: flip to
        'Sales Order' while a submitted Sales Order Item back-links here, and revert to
        'Open' when none remain. Terminal manual statuses (Rejected/Expired) are kept.
        Called from the Sales Order on_submit / on_cancel hook."""
        if self.docstatus != 1:
            return

        has_order = bool(
            frappe.db.exists("Sales Order Item", {
                             "service_quotation": self.name, "docstatus": 1})
        )
        if has_order:
            status = "Sales Order"
        elif self.status in ("Rejected", "Expired"):
            status = self.status
        else:
            status = "Open"

        if self.status != status:
            self.db_set("status", status, update_modified=False)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def validate_valid_till(self):
        if not self.valid_till:
            return
        if getdate(self.valid_till) < getdate(self.transaction_date):
            frappe.throw(
                _("'Valid Till' ({0}) cannot be before the quotation date ({1})").format(
                    self.valid_till, self.transaction_date
                )
            )

    # -------------------------------------------------------------------------
    # Permission helpers
    # -------------------------------------------------------------------------

    def assert_role(self, roles):
        user_roles = frappe.get_roles(frappe.session.user)
        if not any(r in user_roles for r in roles):
            frappe.throw(
                _("You do not have permission to perform this action. Required role(s): {0}").format(
                    ", ".join(roles)
                ),
                frappe.PermissionError,
            )

    def assert_status(self, allowed_statuses):
        if self.status not in allowed_statuses:
            frappe.throw(
                _("This action is not allowed when the quotation status is '{0}'").format(
                    self.status)
            )


# ============================================================================
# PRICING & TOTALS
# ============================================================================
# The previous container/removal-mechanism pricing and totals engine was removed:
# it priced against fields that no longer exist on the doctype and used the old
# discount-based Service Pricing Rule model. The replacement resolves rates via
# the two-layer Container Price / Service Pricing Rule design documented under
# docs/pricing/ and reuses the shared helpers in naqel.utils.pricing
# (get_division_ancestors, assert_single_pricing_rule). To be implemented.


# ============================================================================
# WASTE CONFIGURATION RESOLUTION
# ============================================================================
# The configuration that drives waste calculation for a quotation can come from
# two doctypes:
#   - Service Configuration (SC): the default, keyed by (service_type, ISIC node).
#     A facility carries the leaf Activity ISIC; resolution walks Activity -> Section
#     and takes the first enabled match (a general configuration wins outright).
#   - Regional Service Configuration (RSC): a per-Address-Division override that wraps
#     one SC. Resolution walks the division hierarchy from the territory upward
#     (District -> Province), capped at the level the client provided.
# When Service Type.apply_regional_configuration is on and a territory is given, the
# two hierarchies are combined per Service Type.regional_resolution_method.


def resolve_waste_configuration(service_type, isic_classification, territory=None):
    """Return ``(calculation_based_on, config_name)`` for the winning configuration.

    Returns ``(None, None)`` when nothing can be resolved (e.g. no configuration
    exists yet); the ``reqd`` check on ``service_configuration`` then reports it.
    """
    if not service_type or not isic_classification:
        return (None, None)

    default_sc = _resolve_default_sc(service_type, isic_classification)

    service_type_settings = frappe.db.get_value(
        "Service Type",
        service_type,
        ["apply_regional_configuration", "regional_resolution_method"],
        as_dict=True,
    ) or {}

    # No regional layer: the default Service Configuration is the answer.
    if not (service_type_settings.get("apply_regional_configuration") and territory):
        return ("Service Configuration", default_sc) if default_sc else (None, None)

    method = service_type_settings.get(
        "regional_resolution_method") or ADDRESS_FIRST
    isic_candidates = get_isic_ancestors(isic_classification, fetch_all=False)
    division_candidates = _division_candidates(territory)

    if method == ISIC_FIRST:
        return _resolve_isic_first(service_type, default_sc, division_candidates)
    if method == MOST_SPECIFIC:
        return _resolve_most_specific(
            service_type, isic_candidates, division_candidates, default_sc
        )
    return _resolve_address_first(
        service_type, isic_candidates, division_candidates, default_sc
    )


def _resolve_default_sc(service_type, isic_classification):
    """Default Service Configuration name (general first, then ISIC walk); None if absent.

    A non-throwing twin of waste_calculator.get_service_configuration so an
    incomplete draft does not raise mid-edit.
    """
    general = frappe.db.get_value(
        "Service Configuration",
        {"disabled": 0, "is_general_configuration": 1, "service_type": service_type},
        "name",
    )
    if general:
        return general

    for current_isic in get_isic_ancestors(isic_classification, fetch_all=False):
        name = frappe.db.get_value(
            "Service Configuration",
            {"disabled": 0, "isic_classification": current_isic,
                "service_type": service_type},
            "name",
        )
        if name:
            return name
    return None


def _division_candidates(territory):
    """Address Division names from ``territory`` up to the root, most specific first.

    The territory is collected at the Service Type's assigned level, so its ancestors
    are exactly that level and coarser — naturally capping the regional match.
    """
    node = frappe.db.get_value("Address Division", territory, [
                               "lft", "rgt"], as_dict=True)
    if not node:
        return []
    return frappe.db.sql_list(
        """SELECT name FROM `tabAddress Division`
           WHERE lft <= %s AND rgt >= %s ORDER BY lft DESC""",
        (node.lft, node.rgt),
    )


def _rsc_general(service_type, division):
    """Enabled RSC for this division whose linked SC is a general configuration."""
    RSC = frappe.qb.DocType("Regional Service Configuration")
    SC = frappe.qb.DocType("Service Configuration")
    rows = (
        frappe.qb.from_(RSC)
        .join(SC).on(SC.name == RSC.service_configuration)
        .select(RSC.name)
        .where(RSC.disabled == 0)
        .where(RSC.service_type == service_type)
        .where(RSC.division == division)
        .where(SC.is_general_configuration == 1)
        .limit(1)
        .run()
    )
    return rows[0][0] if rows else None


def _rsc_by_isic(service_type, division, isic):
    """Enabled RSC for this division scoped to a specific ISIC node."""
    RSC = frappe.qb.DocType("Regional Service Configuration")
    rows = (
        frappe.qb.from_(RSC)
        .select(RSC.name)
        .where(RSC.disabled == 0)
        .where(RSC.service_type == service_type)
        .where(RSC.division == division)
        .where(RSC.isic_classification == isic)
        .limit(1)
        .run()
    )
    return rows[0][0] if rows else None


def _rsc_by_config(service_type, division, service_configuration):
    """Enabled RSC for this division that wraps a specific Service Configuration."""
    if not service_configuration:
        return None
    RSC = frappe.qb.DocType("Regional Service Configuration")
    rows = (
        frappe.qb.from_(RSC)
        .select(RSC.name)
        .where(RSC.disabled == 0)
        .where(RSC.service_type == service_type)
        .where(RSC.division == division)
        .where(RSC.service_configuration == service_configuration)
        .limit(1)
        .run()
    )
    return rows[0][0] if rows else None


def _rsc_for_division(service_type, division, isic_candidates):
    """Best RSC within one division: general first, then the ISIC walk."""
    name = _rsc_general(service_type, division)
    if name:
        return name
    for isic in isic_candidates:
        name = _rsc_by_isic(service_type, division, isic)
        if name:
            return name
    return None


def _resolve_address_first(service_type, isic_candidates, division_candidates, default_sc):
    """Most specific division wins; ISIC walk breaks ties within a division."""
    for division in division_candidates:
        rsc = _rsc_for_division(service_type, division, isic_candidates)
        if rsc:
            return ("Regional Service Configuration", rsc)
    return ("Service Configuration", default_sc) if default_sc else (None, None)


def _resolve_isic_first(service_type, default_sc, division_candidates):
    """Anchor on the default SC, then override only with an RSC that wraps it."""
    if default_sc:
        for division in division_candidates:
            rsc = _rsc_by_config(service_type, division, default_sc)
            if rsc:
                return ("Regional Service Configuration", rsc)
    return ("Service Configuration", default_sc) if default_sc else (None, None)


def _resolve_most_specific(service_type, isic_candidates, division_candidates, default_sc):
    """Smallest combined (ISIC + division) distance wins; a regional match wins ties.

    Each rank is the 0-based index into its leaf->root candidate list. The default SC
    is treated as one step beyond the coarsest division so a much more specific ISIC
    configuration can still beat a coarse regional one.
    """
    best_rank = None
    best = (None, None)
    for division_rank, division in enumerate(division_candidates):
        rsc = _rsc_general(service_type, division)
        isic_rank = 0
        if not rsc:
            for index, isic in enumerate(isic_candidates):
                match = _rsc_by_isic(service_type, division, isic)
                if match:
                    rsc, isic_rank = match, index
                    break
        if rsc is None:
            continue
        rank = division_rank + isic_rank
        if best_rank is None or rank < best_rank:
            best_rank, best = rank, ("Regional Service Configuration", rsc)

    if default_sc:
        sc_rank = _sc_isic_rank(
            default_sc, isic_candidates) + len(division_candidates)
        # Regional wins ties, so the SC must be strictly more specific to win.
        if best_rank is None or sc_rank < best_rank:
            return ("Service Configuration", default_sc)

    return best if best[1] else ((None, None))


def _sc_isic_rank(service_configuration, isic_candidates):
    """Depth of a Service Configuration's ISIC node within the leaf->root walk."""
    info = frappe.db.get_value(
        "Service Configuration",
        service_configuration,
        ["is_general_configuration", "isic_classification"],
        as_dict=True,
    )
    if not info or info.is_general_configuration:
        return 0
    try:
        return isic_candidates.index(info.isic_classification)
    except ValueError:
        return len(isic_candidates)


@frappe.whitelist()
def get_resolved_configuration(service_type, facility=None, isic_classification=None, territory=None):
    """Client helper: resolve the auto configuration for the current form state."""
    if not isic_classification and facility:
        isic_classification = frappe.db.get_value(
            "Facility", facility, "isic_classification")
    based_on, config = resolve_waste_configuration(
        service_type, isic_classification, territory)
    return {"calculation_based_on": based_on, "service_configuration": config}


# ============================================================================
# LINK FIELD QUERY FUNCTIONS  (manual picker; used via set_query({ query: "..." }))
# ============================================================================


@frappe.whitelist()
def query_service_configurations(doctype, txt, searchfield, start, page_len, filters):
    """Enabled Service Configurations matching the service type and the facility's
    ISIC Classification or any of its ancestors (or general configurations)."""
    filters = frappe.parse_json(filters) if isinstance(
        filters, str) else (filters or {})
    service_type = filters.get("service_type")
    isic_classification = filters.get("isic_classification")
    if not service_type:
        return []

    SC = frappe.qb.DocType("Service Configuration")
    ancestors = get_isic_ancestors(isic_classification, fetch_all=True)
    if ancestors:
        isic_cond = (SC.is_general_configuration == 1) | (
            SC.isic_classification.isin(ancestors))
    else:
        isic_cond = SC.is_general_configuration == 1

    query = (
        frappe.qb.from_(SC)
        .select(SC.name, SC.service_type, SC.isic_classification)
        .where(SC.disabled == 0)
        .where(SC.service_type == service_type)
        .where(isic_cond)
    )
    if txt:
        query = query.where(SC.name.like(f"%{txt}%"))
    return query.offset(int(start)).limit(int(page_len)).run()


@frappe.whitelist()
def query_regional_service_configurations(doctype, txt, searchfield, start, page_len, filters):
    """Enabled Regional Service Configurations matching the service type, any division
    in the territory's ancestor chain, and the facility's ISIC walk (or general)."""
    filters = frappe.parse_json(filters) if isinstance(
        filters, str) else (filters or {})
    service_type = filters.get("service_type")
    isic_classification = filters.get("isic_classification")
    territory = filters.get("territory")
    if not service_type or not territory:
        return []

    divisions = _division_candidates(territory)
    if not divisions:
        return []

    RSC = frappe.qb.DocType("Regional Service Configuration")
    SC = frappe.qb.DocType("Service Configuration")
    ancestors = get_isic_ancestors(isic_classification, fetch_all=True)
    if ancestors:
        isic_cond = (SC.is_general_configuration == 1) | (
            RSC.isic_classification.isin(ancestors))
    else:
        isic_cond = SC.is_general_configuration == 1

    query = (
        frappe.qb.from_(RSC)
        .join(SC).on(SC.name == RSC.service_configuration)
        .select(RSC.name, RSC.service_type, RSC.division)
        .where(RSC.disabled == 0)
        .where(RSC.service_type == service_type)
        .where(RSC.division.isin(divisions))
        .where(isic_cond)
    )
    if txt:
        query = query.where(RSC.name.like(f"%{txt}%"))
    return query.offset(int(start)).limit(int(page_len)).run()


# ============================================================================
# SERVICE PRICING CALCULATION  ("Calculate Service Pricing" button)
# ============================================================================
# Separation of concern: the resolved `service_configuration` (Service Configuration
# OR Regional Service Configuration) is the single source of truth — the calculator
# consumes it as-is and never re-resolves by ISIC. It reuses the Waste Calculator
# helpers (same field names work for SC and Reconfiguration RSC). For a Safety-Factor
# RSC, the base SC drives the math and the result is scaled by the safety factor.


@frappe.whitelist()
def calculate_service_pricing(doc):
    """Compute the suggested container from the resolved configuration and return a
    single Service Quotation Container row (with all derived fields populated)."""
    if isinstance(doc, str):
        doc = frappe.parse_json(doc)
    doc = frappe._dict(doc)

    if not doc.calculation_based_on or not doc.service_configuration:
        frappe.throw(_("Resolve a Service Configuration before calculating."))
    if not doc.facility_uom:
        frappe.throw(_("Select a Facility UOM before calculating."))

    from naqel.nq_setup.doctype.waste_calculator.waste_calculator import (
        build_generated_container_rows,
        calculate_facility_measurement,
        compute_waste_totals,
        resolve_calculation_config,
    )

    # The calculator helpers read the composite breakdown from `facility_measurements`.
    doc.facility_measurements = doc.get("facility_uoms") or []

    config_doc, safety_multiplier = resolve_calculation_config(
        doc.calculation_based_on, doc.service_configuration
    )

    # Validates whole-number rules per UOM and returns the composite product / single value.
    facility_measurement = calculate_facility_measurement(doc)
    if facility_measurement <= 0:
        frappe.throw(_("Facility measurement must be greater than 0."))

    conversion_factor = flt(doc.get("conversion_factor")) or 1
    net_facility_measurement = facility_measurement * conversion_factor

    # The facility's rating drives the rating safety factor, read from the chosen
    # configuration's Rating Classification.
    facility_rating = frappe.db.get_value(
        "Facility", doc.facility, "rating") if doc.get("facility") else None

    # Shared post-resolution math (base waste + rating/regional multipliers + total).
    totals = compute_waste_totals(
        config_doc,
        safety_multiplier,
        net_facility_measurement,
        doc,
        rating_config_name=doc.service_configuration,
        facility_rating=facility_rating,
    )
    calc_result = totals.calc_result
    generation_rate = totals.generation_rate
    facility_generated_waste = totals.facility_generated_waste
    rating_safety_factor = totals.rating_safety_factor
    regional_safety_factor = totals.regional_safety_factor
    total_generated_waste = totals.total_generated_waste

    default_volume_unit = config_doc.default_volume_unit

    # When nothing scaled the waste, prefer the cluster's own container suggestion;
    # otherwise the shared builder re-suggests against the (scaled) total.
    single_suggestion = None
    if safety_multiplier == 1 and calc_result.get("container_type") and calc_result.get("container_count"):
        single_suggestion = {
            "container": calc_result["container_type"], "count": calc_result["container_count"]}

    # Shared with the Waste Calculator's generated_wastes — identical row shape.
    containers = build_generated_container_rows(
        config_doc,
        default_volume_unit,
        total_generated_waste,
        facility_generated_waste,
        generation_rate,
        regional_safety_factor,
        rating_safety_factor,
        service_type=doc.service_type,
        single_suggestion=single_suggestion,
    )
    if not containers:
        frappe.throw(
            _("No container could be determined for the calculated waste."))

    # Resolve a rate for each suggested container (two-layer pricing) and price the line.
    _price_containers(doc, containers)

    return {
        "containers": containers,
        "total_container_count": sum(r["container_count"] for r in containers),
        "total_volume": sum(r["total_volume"] for r in containers),
        "total_generated_waste": total_generated_waste,
        "total": sum(r.get("amount", 0) for r in containers),
    }


def _price_containers(doc, containers):
    """Resolve each container row's native rate via the two-layer engine, convert it to
    the quotation currency, and populate the rate ladder (ERPNext Quotation Item style):
    default_container_price (preserved) → container_price (editable) → amount, each with
    a company-currency base_* twin."""
    from naqel.utils.pricing import resolve_container_rate

    service_type = doc.get("service_type")
    address_division = doc.get("territory")
    company = doc.get("company")
    sq_currency = doc.get("currency")
    transaction_date = doc.get("transaction_date")
    conversion_rate = flt(doc.get("conversion_rate")) or 1.0

    duration_factor = 1
    if doc.get("mode_of_service") == "Duration-Based" and flt(doc.get("service_duration")):
        duration_factor = flt(doc.get("service_duration"))

    for row in containers:
        rate, native_currency = resolve_container_rate(
            service_type,
            row["container_type"],
            address_division,
            company,
            row.get("collection_mechanism"),
            row.get("collection_count"),
            row.get("collection_period_count"),
            row.get("collection_period_uom"),
            transaction_date,
        )

        # Reconcile the native rate to the document currency (native rates are stored as-is).
        if native_currency and sq_currency and native_currency != sq_currency:
            from erpnext.setup.utils import get_exchange_rate
            rate = flt(rate) * flt(get_exchange_rate(native_currency,
                                                     sq_currency, transaction_date))
        rate = flt(rate)

        count = cint(row.get("container_count") or 1)
        amount = rate * count * duration_factor

        # default_* preserves the calculated price; container_price starts equal and is editable.
        row["default_container_price"] = rate
        row["container_price"] = rate
        row["amount"] = amount
        # Company-currency twins.
        row["base_default_container_price"] = rate * conversion_rate
        row["base_container_price"] = rate * conversion_rate
        row["base_amount"] = amount * conversion_rate


@frappe.whitelist()
def get_quotation_conversion_rate(currency, company, transaction_date=None):
    """Exchange rate from the document currency to the company's base currency
    (1.0 when they match), used to populate the base_* company-currency fields."""
    if not currency or not company:
        return 1.0
    company_currency = frappe.get_cached_value(
        "Company", company, "default_currency")
    if not company_currency or currency == company_currency:
        return 1.0
    from erpnext.setup.utils import get_exchange_rate
    return flt(get_exchange_rate(currency, company_currency, transaction_date)) or 1.0


# ============================================================================
# WORKFLOW ACTION METHODS  (whitelisted so JS can call them via frappe.call)
# ============================================================================

@frappe.whitelist()
def accept_quotation(docname):
    """Customer: Accept the quotation."""
    doc = frappe.get_doc("Service Quotation", docname)
    doc.assert_role(["Customer", "System Manager"])
    doc.assert_status(["Open"])

    frappe.db.set_value("Service Quotation", docname, "status", "Accepted")
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Service Quotation",
        "reference_name": docname,
        "content": _("Customer has accepted the quotation."),
    }).insert(ignore_permissions=True)


@frappe.whitelist()
def reject_quotation(docname, reason):
    """Customer: Reject the quotation."""
    doc = frappe.get_doc("Service Quotation", docname)
    doc.assert_role(["Customer", "System Manager"])
    doc.assert_status(["Open"])

    frappe.db.set_value("Service Quotation", docname, "status", "Rejected")
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Service Quotation",
        "reference_name": docname,
        "content": _("Customer rejected the quotation. Reason: {0}").format(reason),
    }).insert(ignore_permissions=True)


# ============================================================================
# SALES ORDER CREATION  (Create → Sales Order, mirrors ERPNext's Quotation)
# ============================================================================

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
    return _make_sales_order(source_name, target_doc)


def _make_sales_order(source_name, target_doc=None, ignore_permissions=False):
    """Map a Service Quotation to a Sales Order. The billed service line uses the
    Service Type's linked Item priced at the quotation's net total; the additional
    Items and the taxes carry over. The customer is resolved (converting a Lead when
    needed) and linked back into the Facility."""
    from frappe.model.mapper import get_mapped_doc

    source = frappe.get_doc("Service Quotation", source_name)

    if not frappe.db.get_single_value(
        "Selling Settings", "allow_sales_order_creation_for_expired_quotation"
    ):
        if source.valid_till and (
            getdate(source.valid_till) < getdate(source.transaction_date)
            or getdate(source.valid_till) < getdate(nowdate())
        ):
            frappe.throw(_("Validity period of this quotation has ended."))

    service_item = frappe.db.get_value(
        "Service Type", source.service_type, "item")
    if not service_item:
        frappe.throw(
            _("Service Type {0} has no linked Item, so a Sales Order can't be created.").format(
                frappe.bold(source.service_type)
            )
        )

    customer = _make_customer(source, ignore_permissions)
    delivery_date = source.start_date or source.transaction_date

    def set_missing_values(src, target):
        target.customer = customer.name
        target.customer_name = customer.customer_name
        target.delivery_date = delivery_date
        # The priced container total becomes the primary service line (back-linked to
        # the quotation so the Sales Order status tracking can find it).
        if flt(src.net_total):
            target.append("items", {
                "item_code": service_item,
                "qty": 1,
                "rate": flt(src.net_total),
                "delivery_date": delivery_date,
                "service_quotation": src.name,
            })
        target.flags.ignore_permissions = ignore_permissions
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

    def update_item(obj, target, source_parent):
        target.delivery_date = delivery_date

    doclist = get_mapped_doc(
        "Service Quotation",
        source_name,
        {
            "Service Quotation": {
                "doctype": "Sales Order",
                "validation": {"docstatus": ["=", 1]},
            },
            "Service Quotation Item": {
                "doctype": "Sales Order Item",
                "field_map": {"parent": "service_quotation", "name": "service_quotation_item"},
                "postprocess": update_item,
                "condition": lambda row: row.item_code,
            },
            "Sales Taxes and Charges": {
                "doctype": "Sales Taxes and Charges",
            },
        },
        target_doc,
        set_missing_values,
        ignore_permissions=ignore_permissions,
    )
    return doclist


def _make_customer(source, ignore_permissions=False):
    """Resolve the Sales Order customer from the quotation's party (mirrors ERPNext):
    a Customer is used as-is; a Lead is converted to a Customer (reusing an existing
    one). The resolved customer is then linked into the Facility's links table."""
    party_type = source.quotation_to
    party = source.party_name
    if not party:
        frappe.throw(_("Select a Party before creating a Sales Order."))

    if party_type == "Customer":
        customer = frappe.get_doc("Customer", party)
    elif party_type == "Lead":
        existing = frappe.db.get_value("Customer", {"lead_name": party})
        if existing:
            customer = frappe.get_doc("Customer", existing)
        else:
            from erpnext.crm.doctype.lead.lead import _make_customer as create_customer_from_lead

            customer = create_customer_from_lead(
                party, ignore_permissions=ignore_permissions)
            customer.flags.ignore_permissions = ignore_permissions
            customer.insert(ignore_permissions=ignore_permissions)
    else:
        frappe.throw(_("Quotation To must be a Customer or a Lead."))

    _link_customer_to_facility(source.facility, customer.name)
    return customer


def _link_customer_to_facility(facility, customer):
    """Append the customer to the Facility's links (Dynamic Link) if not already present."""
    if not facility or not customer:
        return
    if frappe.db.exists(
        "Dynamic Link",
        {"parenttype": "Facility", "parent": facility,
            "link_doctype": "Customer", "link_name": customer},
    ):
        return
    facility_doc = frappe.get_doc("Facility", facility)
    facility_doc.append(
        "links", {"link_doctype": "Customer", "link_name": customer})
    facility_doc.save(ignore_permissions=True)


# ============================================================================
# SCHEDULED TASK  (called daily via hooks.py)
# ============================================================================

def set_expired_status():
    """Mark Open quotations whose valid_till has passed as Expired."""
    frappe.db.sql("""
        UPDATE `tabService Quotation`
        SET status = 'Expired'
        WHERE docstatus = 1
          AND status = 'Open'
          AND valid_till IS NOT NULL
          AND valid_till < %s
    """, nowdate())


# ============================================================================
# PERMISSION FUNCTIONS  (auto-discovered by Frappe for desk access)
# ============================================================================

def has_permission(doc, _ptype, user):
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return True

    if "Customer" in frappe.get_roles(user):
        from naqel.nq_crm.doctype.facility.facility import get_customer_names_for_user
        customer_names = get_customer_names_for_user(user)
        if not customer_names:
            return False
        if doc:
            return doc.customer in customer_names
        return True

    return True


def get_permission_query_conditions(user):
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return None

    if "Customer" in frappe.get_roles(user):
        from naqel.nq_crm.doctype.facility.facility import get_customer_names_for_user
        customer_names = get_customer_names_for_user(user)
        if not customer_names:
            return "1=0"
        if len(customer_names) == 1:
            return f"`tabService Quotation`.`customer` = {frappe.db.escape(customer_names[0])}"
        customer_list = ", ".join(frappe.db.escape(c) for c in customer_names)
        return f"`tabService Quotation`.`customer` IN ({customer_list})"

    return None
