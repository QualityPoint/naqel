# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.contacts.address_and_contact import (
    delete_contact_and_address,
    load_address_and_contact,
    set_link_title,
)
from naqel.utils.geolocation import (
    sync_geolocation_to_floats,
    sync_floats_to_geolocation
)
from frappe.utils.nestedset import NestedSet


# Address field (target) -> Facility field (source). Facility is the source of truth;
# shared by create_address (insert) and sync_linked_address (update).
FACILITY_ADDRESS_FIELD_MAP = {
    "address_line1": "street",
    "building_no": "building_no",
    "secondary_no": "secondary_no",
    "city": "city",
    "district": "district",
    "pincode": "pincode",
    "country": "country",
}


class Facility(NestedSet):
    nsm_parent_field = "parent_facility"

    def onload(self):
        load_address_and_contact(self)

    def before_validate(self):
        self.set_location_from_parent()

    def before_insert(self):
        # Auto-create the Facility's Address from its own address fields, mirroring
        # how Lead auto-creates a Contact. Built (and inserted) here without a link
        # because the Facility has no name yet; linked back in after_insert. This
        # dissolves the "linked address required" deadlock on new facilities.
        self._address_doc = None
        if self.should_create_address():
            self._address_doc = self.create_address()

    def after_insert(self):
        self.link_address()

    def should_create_address(self):
        # Sub-facilities inherit the parent's address unless explicitly allowed.
        if self.parent_facility and not frappe.db.get_single_value(
            "Address Settings", "allow_different_address_for_sub_facility"
        ):
            return False
        # Only when the facility actually carries its own street address.
        return bool(self.street)

    def create_address(self):
        """Build & insert an Address from the Facility's address fields.

        Maps the national-address parts to Address: street → address_line1, plus the
        building_no / secondary_no / district custom fields, and city / pincode /
        country. ignore_mandatory keeps a missing field from blocking creation.
        """
        address = frappe.new_doc("Address")
        address.update(
            {
                "address_title": self.facility_name or self.name,
                "address_type": "Plant",
            }
        )
        for address_field, facility_field in FACILITY_ADDRESS_FIELD_MAP.items():
            address.set(address_field, self.get(facility_field))
        address.flags.ignore_permissions = True
        address.flags.ignore_mandatory = True
        address.insert()
        return address

    def link_address(self):
        address = getattr(self, "_address_doc", None)
        if not address:
            return
        address.append(
            "links",
            {
                "link_doctype": "Facility",
                "link_name": self.name,
                "link_title": self.facility_name,
            },
        )
        address.flags.ignore_permissions = True
        address.save()

    def sync_linked_address(self):
        """Re-save the linked Address when the Facility's address changes.

        One-way (Facility is the source of truth). Runs on update only; the insert
        flow is handled by create_address/link_address. The actual field copy is done
        by overrides.address.enforce_facility_address_source on the Address save, so
        it stays in one place. No-ops when nothing changed or no Address is linked.
        """
        if not any(self.has_value_changed(f) for f in FACILITY_ADDRESS_FIELD_MAP.values()):
            return

        address_name = frappe.db.get_value(
            "Dynamic Link",
            {"parenttype": "Address", "link_doctype": "Facility",
                "link_name": self.name},
            "parent",
        )
        if not address_name:
            return

        address = frappe.get_doc("Address", address_name)
        address.flags.ignore_permissions = True
        address.save()

    def set_location_from_parent(self):
        if not self.parent_facility:
            return
        allow_different = frappe.db.get_single_value(
            "Address Settings", "allow_different_address_for_sub_facility"
        )
        if allow_different:
            return
        parent = frappe.db.get_value(
            "Facility", self.parent_facility, ["location", "latitude", "longitude"], as_dict=True
        )
        if parent:
            self.location = parent.location
            self.latitude = parent.latitude
            self.longitude = parent.longitude

    def clear_parent_facility_if_is_group(self):
        """If 'Has Multiple Branches' is checked, clear the 'Parent Facility' field to avoid confusion."""
        if self.is_group:
            self.parent_facility = None

    def validate(self):
        set_link_title(self)
        self.validate_allowed_link_types()
        self.validate_single_party_per_type()
        self.set_party_from_links()
        self.clear_parent_facility_if_is_group()
        self.sync_location_fields()
        self.validate_parent_is_group()
        self.validate_has_children_if_not_group()
        self.validate_unique_document_number()
        self.validate_geolocation()
        self.apply_territory_settings()
        self.validate_facility_credentials()

    def set_party_from_links(self):
        """Derive the effective party from the Links table.

        A facility may be linked to a Customer and/or a Lead (e.g. mid-conversion).
        Following the CRM cycle, a Customer takes precedence over a Lead.
        """
        customer = lead = None
        for link in self.links:
            if link.link_doctype == "Customer" and not customer:
                customer = link.link_name
            elif link.link_doctype == "Lead" and not lead:
                lead = link.link_name

        if customer:
            self.party_type, self.party = "Customer", customer
        elif lead:
            self.party_type, self.party = "Lead", lead
        else:
            self.party_type, self.party = None, None

    def validate_allowed_link_types(self):
        """A Facility may only be linked to a Customer or a Lead."""
        allowed_link_types = ("Customer", "Lead")
        for link in self.links:
            if link.link_doctype not in allowed_link_types:
                frappe.throw(
                    _("A Facility can only be linked to a {0}, not {1}.").format(
                        _(" or ").join(_(dt) for dt in allowed_link_types),
                        _(link.link_doctype),
                    )
                )

    def validate_single_party_per_type(self):
        """A Facility may be linked to at most one Customer and one Lead."""
        allowed_link_types = ("Customer", "Lead")
        counts = {}
        for link in self.links:
            counts[link.link_doctype] = counts.get(link.link_doctype, 0) + 1

        for party_type in allowed_link_types:
            if counts.get(party_type, 0) > 1:
                frappe.throw(
                    _("A Facility can be linked to only one {0}.").format(
                        _(party_type))
                )

    def validate_geolocation(self):
        requires = frappe.db.get_single_value(
            'Address Settings', 'requires_pinned_location')
        if requires and not self.location:
            frappe.throw(
                _("A map location is required. Please pin the facility's location on the map."),
                title=_("Geolocation Required")
            )

    def apply_territory_settings(self):
        """Mirror the global Service Settings territory policy onto this Facility.

        Service Settings is the single source of truth. When territory assignment
        is required, copy the configured division category down (into the read-only
        mirror fields), enforce that a Territory is set, and that the chosen
        Address Division actually belongs to the configured category. When it is
        not required, clear the mirror so the Facility never carries a stale policy.
        """
        settings = frappe.get_cached_doc("Service Settings")
        self.assign_territory = settings.requires_assigning_territory

        if not self.assign_territory:
            self.address_division_category = None
            return

        self.address_division_category = settings.assigned_address_division_category

        if not self.territory:
            frappe.throw(
                _("Territory is required. Please assign a {0}-level Address Division.").format(
                    _(self.address_division_category)
                ),
                title=_("Territory Required"),
            )

        division = frappe.db.get_value(
            "Address Division", self.territory, ["division_category", "country"], as_dict=True
        )
        if division.division_category != self.address_division_category:
            frappe.throw(
                _("Territory '{0}' is a {1}, but a {2}-level Address Division is required.").format(
                    self.territory, _(division.division_category), _(
                        self.address_division_category)
                ),
                title=_("Invalid Territory"),
            )
        if self.country and division.country and division.country != self.country:
            frappe.throw(
                _("Territory '{0}' belongs to {1}, but this Facility is in {2}.").format(
                    self.territory, division.country, self.country
                ),
                title=_("Invalid Territory"),
            )

    def validate_facility_credentials(self):
        """Enforce the global facility-credential policy from Service Settings.

        When ``requires_facility_credentials`` is on, the Facility must carry at
        least one credential. When the allowed types are configured, each row's
        credential_type / document_type must be among them. When
        ``upload_facility_credential`` is on, each row must have its document
        actually attached. Mirrors the desk-form behaviour for non-UI saves.
        """
        settings = frappe.get_cached_doc("Service Settings")
        if not settings.requires_facility_credentials:
            return

        if not self.credentials:
            frappe.throw(
                _("At least one credential is required for this Facility."),
                title=_("Credentials Required"),
            )

        # Allowed {credential_type: {document_types}} from the settings table.
        allowed = {}
        for row in settings.credentials:
            if row.credential_type:
                allowed.setdefault(row.credential_type, set())
                if row.document_type:
                    allowed[row.credential_type].add(row.document_type)

        upload_required = settings.upload_facility_credential

        for row in self.credentials:
            # Restrict types only when the admin has actually configured them.
            if allowed:
                if row.credential_type not in allowed:
                    frappe.throw(
                        _("Row #{0}: Credential Type '{1}' is not permitted.").format(
                            row.idx, row.credential_type
                        ),
                        title=_("Invalid Credential"),
                    )
                allowed_docs = allowed[row.credential_type]
                if allowed_docs and row.document_type not in allowed_docs:
                    frappe.throw(
                        _("Row #{0}: Document Type '{1}' is not permitted for '{2}'.").format(
                            row.idx, row.document_type, row.credential_type
                        ),
                        title=_("Invalid Credential"),
                    )

            if upload_required and not row.credential:
                frappe.throw(
                    _("Row #{0}: Please upload the credential document for '{1}'.").format(
                        row.idx, row.document_type or row.credential_type
                    ),
                    title=_("Credential Upload Required"),
                )

    def sync_location_fields(self):
        """Synchronize between Geolocation field and Float latitude/longitude fields"""
        # Check which field was modified
        if self.has_value_changed('location'):
            # Geolocation field was updated, sync to float fields
            sync_geolocation_to_floats(
                self, 'location', 'latitude', 'longitude')
        elif self.has_value_changed('latitude') or self.has_value_changed('longitude'):
            # Float fields were updated, sync to geolocation
            sync_floats_to_geolocation(
                self, 'latitude', 'longitude', 'location')

    def validate_parent_is_group(self):
        """Validate that parent_facility has is_group checked"""
        if not self.parent_facility:
            return

        parent_facility = frappe.db.get_value(
            "Facility", self.parent_facility, ["is_group", "party_type", "party"], as_dict=True)

        if not parent_facility.is_group:
            frappe.throw(
                _("Parent Facility '{0}' must have 'Has Multiple Branches' enabled to have child facilities.").format(
                    self.parent_facility
                )
            )

        if (parent_facility.party_type, parent_facility.party) != (self.party_type, self.party):
            frappe.throw(
                _("Parent Facility must belong to the same party as the child facility.")
            )

    def validate_has_children_if_not_group(self):
        """Prevent unchecking is_group if facility has children"""
        if self.is_group:
            return

        # Check if this facility has any children
        has_children = frappe.db.exists(
            "Facility",
            {
                "parent_facility": self.name
            }
        )

        if has_children:
            frappe.throw(
                _("Cannot disable 'Has Multiple Branches' because this facility has child branches. Please remove all child facilities first.")
            )

    def validate_unique_document_number(self):
        """
        Validate credential document numbers in the child table:
        1. If is_group: must have at least one credential with eligible_for_multiple_facility_branches.
        2. Non-eligible credentials: document_number must be globally unique per document_type.
        3. Eligible credentials in a branch: document_number must match parent's credential exactly.
        4. Eligible credentials in a group facility: no uniqueness check.
        """
        if self.is_group:
            has_eligible = any(
                row.eligible_for_multiple_facility_branches
                for row in self.credentials
            )
            if not has_eligible:
                frappe.throw(
                    _("A facility with multiple branches must have at least one credential "
                      "with 'Eligible For Multi-branched Facility' enabled."),
                    title=_("Missing Eligible Credential")
                )

        parent_credentials = {}
        if self.parent_facility:
            parent_creds = frappe.get_all(
                "Facility Credential",
                filters={"parent": self.parent_facility,
                         "parenttype": "Facility"},
                fields=["document_type", "document_number"],
            )
            parent_credentials = {
                r.document_type: r.document_number for r in parent_creds}

        for row in self.credentials:
            if not row.eligible_for_multiple_facility_branches:
                existing = frappe.db.exists(
                    "Facility Credential",
                    {
                        "document_type": row.document_type,
                        "document_number": row.document_number,
                        "parent": ["!=", self.name],
                        "parenttype": "Facility",
                    },
                )
                if existing:
                    frappe.throw(
                        _("Row #{0}: Document Number '{1}' for '{2}' is already used by another facility.").format(
                            row.idx, row.document_number, row.document_type
                        ),
                        title=_("Duplicate Document Number"),
                    )
            elif self.parent_facility:
                expected = parent_credentials.get(row.document_type)
                if expected is None:
                    frappe.throw(
                        _("Row #{0}: Document Type '{1}' is not found in the parent facility's credentials.").format(
                            row.idx, row.document_type
                        ),
                        title=_("Invalid Credential"),
                    )
                if row.document_number != expected:
                    frappe.throw(
                        _("Row #{0}: Document Number for '{1}' must match the parent facility's document number '{2}'.").format(
                            row.idx, row.document_type, expected
                        ),
                        title=_("Document Number Mismatch"),
                    )

    def on_update(self):
        self.update_nsm_model()
        # Insert flow already creates+links the Address (after_insert); only push
        # edits to the existing linked Address on subsequent updates.
        if not self.flags.in_insert:
            self.sync_linked_address()

    def update_nsm_model(self):
        frappe.utils.nestedset.update_nsm(self)

    def on_trash(self):
        NestedSet.validate_if_child_exists(self)
        frappe.utils.nestedset.update_nsm(self)
        # Remove the auto-created Address (and any linked Contact), mirroring Lead.
        delete_contact_and_address("Facility", self.name)


@frappe.whitelist()
def get_eligible_parent_credentials(parent_facility):
    """Return credentials from a parent facility that are eligible for multiple branches."""
    return frappe.get_all(
        "Facility Credential",
        filters={
            "parent": parent_facility,
            "parenttype": "Facility",
            "eligible_for_multiple_facility_branches": 1,
        },
        fields=[
            "credential_type", "document_type", "document_number",
            "has_expiry_date", "eligible_for_multiple_facility_branches",
        ],
    )


@frappe.whitelist()
def get_children(doctype, parent=None, is_root=False, **filters):
    """
    Get children nodes for tree view
    """
    filters_list = []

    fields = ["name as value", "facility_name as title"]

    if is_root:
        # Get all root nodes (no parent)
        filters_list.append(["parent_facility", "in", ["", None]])
    elif parent:
        # Get children of specific parent
        filters_list.append(["parent_facility", "=", parent])
    else:
        # Get all root nodes by default
        filters_list.append(["parent_facility", "in", ["", None]])
    facilities = frappe.get_list(
        doctype,
        fields=fields,
        filters=filters_list,
        order_by="lft"
    )

    # Check if each member has children (is expandable)
    for facility in facilities:
        has_children = frappe.db.exists(
            doctype,
            {"parent_facility": facility.get("value")}
        )
        facility.expandable = 1 if has_children else 0

    return facilities


@frappe.whitelist()
def make_service_quotation(source_name, target_doc=None):
    """Map a Facility to a new Service Quotation (Create → Quotation).

    Mirrors erpnext's "Create Quotation from Lead" (Lead.make_quotation): map the
    source, set the party, then resolve the party-derived display fields on the
    mapped (unsaved) doc so they show immediately — without this, customer_name and
    the rendered addresses stay blank until the first save.

    The facility link, its ISIC Classification and territory map automatically
    (same-named fields / Link-to-Facility); project_name maps explicitly. The party
    is resolved from the Facility's links (Customer wins over Lead, mirroring
    set_party_from_links), and its details + the Facility Address are rendered here.
    The remaining required fields — company, service type, currency, dates,
    configuration, UOM and containers — are completed by the user on the draft.
    """
    from frappe.contacts.doctype.address.address import get_address_display
    from frappe.model.mapper import get_mapped_doc

    from naqel.utils.utils import get_default_address, get_party_details

    def set_missing_values(source, target):
        # Party (and its display name / billing address / contact), resolved from the
        # Facility's links. get_party_details is the same bundle the form's party_name
        # handler applies, so the draft matches a manually-keyed quotation.
        source.set_party_from_links()
        if source.party_type:
            target.quotation_to = source.party_type
            target.party_name = source.party
            target.update(get_party_details(source.party_type, source.party))

        # Facility Address text editor (mirror render_facility_address): render the
        # facility's default linked Address via the Address Template.
        facility_address = get_default_address("Facility", source.name)
        if facility_address:
            target.facility_address = get_address_display(facility_address) or ""

    return get_mapped_doc(
        "Facility",
        source_name,
        {
            "Facility": {
                "doctype": "Service Quotation",
                "field_map": {
                    "name": "facility",
                    "facility_name": "project_name",
                },
            },
        },
        target_doc,
        set_missing_values,
    )


def get_customer_names_for_user(user):
    """Return Customer names where the given user appears in the portal_users table."""
    PortalUser = frappe.qb.DocType("Portal User")
    return (
        frappe.qb.from_(PortalUser)
        .select(PortalUser.parent)
        .where(PortalUser.user == user)
        .where(PortalUser.parenttype == "Customer")
    ).run(pluck="parent")


def has_permission(doc, ptype, user):
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return True

    if "Customer" in frappe.get_roles(user):
        customer_names = get_customer_names_for_user(user)
        if not customer_names:
            return False
        if doc:
            return doc.party_type == "Customer" and doc.party in customer_names
        return True

    # Internal users (Sales, Transporters, etc.) — no additional restriction
    return True


def get_permission_query_conditions(user):
    if "System Manager" in frappe.get_roles(user) or user == "Administrator":
        return None

    if "Customer" in frappe.get_roles(user):
        customer_names = get_customer_names_for_user(user)
        if not customer_names:
            return "1=0"
        customer_list = ", ".join(frappe.db.escape(c) for c in customer_names)
        return (
            f"`tabFacility`.`party_type` = 'Customer' "
            f"AND `tabFacility`.`party` IN ({customer_list})"
        )

    return None


# ---------------------------------------------------------------------------
# National address document parsing
# ---------------------------------------------------------------------------

# Bridge: field names → ParseResult.fields human-readable labels
# (mirrors the keys used in SAParser._flatten_address)
_SPL_LABEL = {
    "ShortAddress": "Short Address",
    "BuildingNumber": "Building Number",
    "Street": "Street",
    "District": "District",
    "City": "City",
    "RegionName": "Region",
    "PostCode": "Post Code",
    "AdditionalNumber": "Additional Number",
}

# Fixed mapping: human label → Facility fieldname (used to map parsed address parts).
_DEFAULT_LABEL_TO_FIELD = {
    "Building Number": "building_no",
    "Street": "street",
    "Post Code": "pincode",
}


@frappe.whitelist()
def parse_national_address(file_url: str) -> dict:
    """
    Parse a national address document (PDF or image) and return structured
    address fields ready to populate the Facility form.

    Config sources:
      - Address Settings: enable_document_parsing, parser_strategy,
                          ocr_language, show_raw_text_in_display
    """
    import re as _re
    from naqel.utils.document_parser.api import _resolve_file_path, _to_tesseract_lang
    from naqel.utils.document_parser.factory import get_parser

    if not file_url:
        frappe.throw(_("file_url is required."))

    addr_settings = frappe.get_cached_doc(
        "Address Settings", "Address Settings")

    if not addr_settings.get("enable_document_parsing"):
        return {
            "success": False,
            "error": _("Document parsing is not enabled in Address Settings."),
            "short_address": "", "fields": {}, "display_html": "",
            "warnings": [], "confirm_before_overwrite": False,
        }

    strategy = addr_settings.get("parser_strategy") or "Auto (by Country)"
    if strategy == "Disabled":
        return {
            "success": False,
            "error": _("Address document parsing is disabled in Address Settings."),
            "short_address": "", "fields": {}, "display_html": "",
            "warnings": [], "confirm_before_overwrite": False,
        }

    file_path = _resolve_file_path(file_url)

    ocr_language = "ara"
    if addr_settings.get("ocr_language"):
        ocr_language = _to_tesseract_lang(addr_settings.get("ocr_language"))

    label_to_field = _build_address_field_map()
    config = {
        "extraction_pattern": addr_settings.get("address_extraction_pattern") or "",
        "designated_field_name": "",
        "ocr_language": ocr_language,
        "parser_type": "OCR" if strategy == "OCR Only" else "QR",
        "raw_text_only": True,
        "targeted_fields": list(label_to_field.keys()),
    }
    if strategy == "QR Code + API":
        config["country"] = "Saudi Arabia"
    elif strategy == "Auto (by Country)":
        config["country"] = frappe.db.get_single_value(
            "System Settings", "country") or ""

    parser = get_parser(config)
    result = parser.parse(file_path)

    # Honour show_raw_text_in_display (default on)
    show_raw = addr_settings.get("show_raw_text_in_display")
    show_raw = True if show_raw is None else bool(show_raw)
    display_html = result.display_html
    if not show_raw:
        display_html = _re.sub(
            r"<details>.*?</details>", "", display_html, flags=_re.DOTALL
        ).strip()

    # Map ParseResult.fields → Facility fields using the fixed default mapping.
    # Supports two key formats from named-group patterns:
    #   1. Human labels  e.g. "Building Number" → label_to_field lookup
    #   2. Snake_case group names e.g. "building_number" → used as-is if they
    #      are already valid facility field names (direct passthrough).
    label_to_field = _build_address_field_map()
    # Build a reverse map: fieldname → fieldname (identity, for group-name keys) so
    # OCR group names that directly match a facility field (e.g. "pincode") are
    # never dropped.
    all_target_fields = set(label_to_field.values()) | set(
        _DEFAULT_LABEL_TO_FIELD.values())
    field_passthrough = {v: v for v in all_target_fields}
    # Aliases for group names that differ from the facility field name.
    # Kept for backward compatibility with patterns saved before the rename.
    group_aliases = {"postal_code": "pincode"}
    combined_map = {**label_to_field, **field_passthrough, **group_aliases}
    mapped = {
        combined_map[label]: value
        for label, value in result.fields.items()
        if label in combined_map
    }

    return {
        "short_address": result.document_number,
        "fields": mapped,
        "display_html": display_html,
        "success": result.success,
        "warnings": result.warnings,
        "error": result.error,
        "confirm_before_overwrite": _get_confirm_before_overwrite(),
    }


def _build_address_field_map() -> dict:
    """Return the default {human_label: facility_fieldname} dict."""
    return dict(_DEFAULT_LABEL_TO_FIELD)


def _get_confirm_before_overwrite() -> bool:
    """Default: always confirm before overwriting address fields."""
    return True
