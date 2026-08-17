# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

"""
Parser factory.

Selects the correct parser implementation based on:
  - parser_type  (from the credential / license / ID setup doc)
  - country      (used by "Auto" strategy)
"""

from naqel.utils.document_parser.base_parser import BaseParser


def get_parser(config: dict) -> BaseParser:
    """
    Return the appropriate parser instance for *config*.

    Args:
        config: dict that must contain at least ``parser_type``.
                Optional keys: ``country``, ``extraction_pattern``,
                ``designated_field_name`` / ``license_field_name``,
                ``ocr_language``.

    Returns:
        A BaseParser subclass instance ready to call `.parse(file_path)`.

    Raises:
        ValueError: if parser_type is unknown or "Manual".
    """
    parser_type: str = (config.get("parser_type") or "").strip()

    if parser_type == "Manual":
        raise ValueError(
            "parser_type is 'Manual' — no automatic parsing configured.")

    if not parser_type:
        raise ValueError("parser_type is required in config.")

    # QR strategy — auto-detect country to pick the right QR handler
    if parser_type == "QR":
        country = _get_country(config)
        if country == "Saudi Arabia":
            from naqel.utils.document_parser.parsers.sa_parser import SAParser
            return SAParser(config)
        # Generic QR: just decode and apply extraction_pattern
        from naqel.utils.document_parser.parsers.generic_parser import GenericParser
        return GenericParser({**config, "parser_type": "QR"})

    if parser_type in ("OCR", "Regex"):
        from naqel.utils.document_parser.parsers.generic_parser import GenericParser
        return GenericParser(config)

    raise ValueError(f"Unknown parser_type: {parser_type!r}")


# ---------------------------------------------------------------------------

def _get_country(config: dict) -> str:
    """
    Resolve the country to use for strategy selection.

    Priority:
      1. config["country"]  — caller can override
      2. "" (unknown)
    """
    return config.get("country") or ""
