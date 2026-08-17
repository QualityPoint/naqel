# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

import os as _os
import frappe
import requests
from frappe import _
from frappe.model.document import Document


class AddressSettings(Document):
    pass


@frappe.whitelist(allow_guest=False)
def get_map_defaults():
    """Return the configured default map center and zoom from Address Settings."""
    settings = frappe.get_single("Address Settings")
    lat = settings.default_map_latitude
    lng = settings.default_map_longitude
    zoom = settings.default_map_zoom or 10

    if lat is not None and lng is not None:
        return {"center": [lat, lng], "zoom": zoom}
    return None


@frappe.whitelist(allow_guest=False)
def fetch_country_coordinates():
    """Look up the centre coordinates of the system's default country via Nominatim."""
    country = frappe.db.get_single_value("System Settings", "country")
    if not country:
        frappe.throw(_("No default country is set in System Settings."),
                     title=_("Country Not Configured"))

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"country": country, "format": "json", "limit": 1},
            headers={"User-Agent": "Naqel/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except Exception as e:
        frappe.throw(_("Failed to fetch coordinates: {0}").format(
            str(e)), title=_("Geocoding Error"))

    if not results:
        frappe.throw(
            _("Could not find coordinates for country '{0}'.").format(country),
            title=_("Country Not Found"),
        )

    return {
        "country": country,
        "latitude": float(results[0]["lat"]),
        "longitude": float(results[0]["lon"]),
    }


# ---------------------------------------------------------------------------
# Extraction pattern templates are stored as individual .regex files under:
#   extraction_templates/<country_slug>.regex
# The country name is lowercased and spaces replaced with underscores to
# produce the slug (e.g. "Saudi Arabia" → "saudi_arabia.regex").
# "global.regex" is always the fallback.
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = _os.path.join(
    _os.path.dirname(__file__), "extraction_templates")


def _load_template(slug: str) -> str | None:
    path = _os.path.join(_TEMPLATES_DIR, f"{slug}.regex")
    if _os.path.isfile(path):
        return open(path, encoding="utf-8").read().strip()
    return None


def _country_slug(country: str) -> str:
    return country.lower().replace(" ", "_")


@frappe.whitelist(allow_guest=False)
def get_extraction_template(country: str = "") -> dict:
    """
    Return the extraction pattern template for the given country.
    Looks for extraction_templates/<country_slug>.regex first,
    then falls back to extraction_templates/global.regex.
    Add a new country by dropping a <slug>.regex file in that folder.
    """
    matched_country = None
    template = None

    if country:
        template = _load_template(_country_slug(country))
        if template:
            matched_country = country

    if not template:
        template = _load_template("global") or ""

    return {
        "template": template,
        "matched_country": matched_country,
    }


@frappe.whitelist(allow_guest=False)
def parse_sample_document(file_url: str) -> dict:
    """
    Run the current parser config against a sample document and return the
    display HTML for the sample_display field.

    Reads all config (strategy, ocr_language, show_raw_text_in_display) from
    the saved Address Settings record — identical to the production flow but
    without field mapping or confirm_before_overwrite.
    """
    import re as _re
    from naqel.utils.document_parser.api import _resolve_file_path, _to_tesseract_lang
    from naqel.utils.document_parser.factory import get_parser

    if not file_url:
        frappe.throw(_("Please attach a sample document first."),
                     title=_("No Sample"))

    settings = frappe.get_single("Address Settings")

    strategy = settings.get("parser_strategy") or "Auto (by Country)"
    if strategy == "Disabled":
        frappe.throw(
            _("Parser Strategy is set to Disabled. Change it to test parsing."),
            title=_("Parsing Disabled"),
        )

    file_path = _resolve_file_path(file_url)

    ocr_language = "ara"
    if settings.get("ocr_language"):
        ocr_language = _to_tesseract_lang(settings.get("ocr_language"))

    # Read the field mapping so OCR Only can hint which fields will be filled.
    try:
        from naqel.nq_crm.doctype.facility.facility import _build_address_field_map
        targeted_fields = list(_build_address_field_map().keys())
    except Exception:
        targeted_fields = []

    config = {
        "extraction_pattern": settings.get("address_extraction_pattern") or "",
        "designated_field_name": "",
        "ocr_language": ocr_language,
        "parser_type": "OCR" if strategy == "OCR Only" else "QR",
        "raw_text_only": True,
        "targeted_fields": targeted_fields,
    }
    if strategy == "QR Code + API":
        config["country"] = "Saudi Arabia"
    elif strategy == "Auto (by Country)":
        config["country"] = frappe.db.get_single_value(
            "System Settings", "country") or ""

    parser = get_parser(config)
    result = parser.parse(file_path)

    display_html = result.display_html
    show_raw = settings.get("show_raw_text_in_display")
    # default is checked (1); only strip when explicitly disabled
    if show_raw == 0:
        display_html = _re.sub(
            r"<details>.*?</details>", "", display_html, flags=_re.DOTALL
        ).strip()

    return {
        "display_html": display_html,
        "success": result.success,
        "warnings": result.warnings,
        "error": result.error,
    }
