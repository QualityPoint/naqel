# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

"""
Whitelisted API for parsing credential documents.

Called from the browser when a file is attached to a credential row
in Facility or Company doctypes.
"""

import os

import frappe
from frappe import _


@frappe.whitelist()
def parse_credential_document(file_url: str, credential_type: str, document_type: str) -> dict:
    """
    Parse a credential document (PDF or image) and extract the document number.

    Args:
        file_url      : Frappe file URL, e.g. "/files/license.pdf" or "/private/files/id.pdf"
        credential_type: The parent DocType of the credential, e.g. "License" or
                         "Identification Number"
        document_type : The name of the specific setup record, e.g. "Commercial Registration"

    Returns:
        dict with keys:
            document_number (str)  — extracted identifier, empty string if not found
            display_html    (str)  — HTML snippet for the document_display Text Editor
            success         (bool)
            warnings        (list[str])
            error           (str)  — non-empty only when success is False
    """
    _validate_inputs(file_url, credential_type, document_type)

    file_path = _resolve_file_path(file_url)
    config = _build_parser_config(credential_type, document_type)

    if config.get("parser_type") == "Manual":
        return {
            "document_number": "",
            "display_html": "",
            "success": False,
            "warnings": [],
            "error": _("This document type is configured for manual entry only."),
        }

    from naqel.utils.document_parser.factory import get_parser

    parser = get_parser(config)
    result = parser.parse(file_path)

    return {
        "document_number": result.document_number,
        "display_html": result.display_html,
        "success": result.success,
        "warnings": result.warnings,
        "error": result.error,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_inputs(file_url: str, credential_type: str, document_type: str) -> None:
    """Basic input sanitisation / permission guard."""
    if not file_url or not credential_type or not document_type:
        frappe.throw(
            _("file_url, credential_type and document_type are all required."))

    allowed_types = {"License", "Identification Number"}
    if credential_type not in allowed_types:
        frappe.throw(
            _("Unsupported credential_type: {0}").format(credential_type))

    if not frappe.db.exists(credential_type, document_type):
        frappe.throw(
            _("{0} '{1}' not found.").format(credential_type, document_type)
        )


def _resolve_file_path(file_url: str) -> str:
    """Convert a Frappe file URL to an absolute path on the server."""
    if file_url.startswith("/files/"):
        path = frappe.get_site_path("public") + file_url
    elif file_url.startswith("/private/files/"):
        path = frappe.get_site_path() + file_url
    else:
        frappe.throw(
            _("Unsupported file URL format: {0}. Expected /files/... or /private/files/...").format(
                file_url
            )
        )

    path = os.path.normpath(path)

    if not os.path.isfile(path):
        frappe.throw(_("File not found on server: {0}").format(file_url))

    return path


_ISO639_1_TO_TESSERACT = {
    "ar": "ara",
    "en": "eng",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "ur": "urd",
    "fa": "fas",
    "tr": "tur",
    "zh": "chi_sim",
}


def _to_tesseract_lang(lang_code: str) -> str:
    """Convert a Frappe Language code (ISO 639-1, e.g. 'ar') to a Tesseract
    language string (ISO 639-2/3, e.g. 'ara'). Falls back to the input value
    unchanged if no mapping is found."""
    return _ISO639_1_TO_TESSERACT.get(lang_code, lang_code)


def _build_parser_config(credential_type: str, document_type: str) -> dict:
    """Collect parser settings from the setup doctype + Address Settings."""
    setup_doc = frappe.get_doc(credential_type, document_type)

    # Resolve the field-label hint (varies by doctype)
    field_label = getattr(setup_doc, "designated_field_name", None) or getattr(
        setup_doc, "license_field_name", None
    ) or ""

    # OCR language comes from Address Settings (Link → Language doctype, ISO 639-1 code)
    ocr_language = "ara"
    try:
        nas = frappe.get_cached_doc("Address Settings", "Address Settings")
        lang_link = nas.get("ocr_language")
        if lang_link:
            ocr_language = _to_tesseract_lang(lang_link)
    except Exception:
        pass

    return {
        "parser_type": setup_doc.get("parser_type") or "Manual",
        "extraction_pattern": setup_doc.get("extraction_pattern") or "",
        "designated_field_name": field_label,
        "ocr_language": ocr_language,
    }
