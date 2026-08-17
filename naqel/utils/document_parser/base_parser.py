# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

"""
Base class for all document parsers.

A parser receives a file path (PDF or image) and a parser config dict,
and returns a ParseResult with extracted text and structured fields.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """Holds the output of a document parse operation."""

    # Raw OCR / decoded text from the document
    raw_text: str = ""

    # Structured key→value fields extracted from the document
    fields: dict[str, Any] = field(default_factory=dict)

    # The primary identifier extracted (e.g. document number / short address code)
    document_number: str = ""

    # Human-readable summary for the document_display Text Editor field
    display_html: str = ""

    # True if parsing succeeded at all (even if field extraction was partial)
    success: bool = False

    # Non-fatal warnings or notes
    warnings: list[str] = field(default_factory=list)

    # Error message if success is False
    error: str = ""


class BaseParser(ABC):
    """
    Abstract base for all document parsers.

    Subclasses implement `parse()` for a specific strategy
    (QR+API, OCR+Regex, etc.).
    """

    def __init__(self, config: dict):
        """
        Args:
            config: dict with keys from the credential/ID/license setup doc:
                - parser_type      : "QR" | "OCR" | "Regex" | "Manual"
                - extraction_pattern: regex string (for OCR / Regex strategies)
                - designated_field_name / license_field_name: label hint
                - ocr_language     : tesseract lang string, default "ara"
        """
        self.config = config
        self.ocr_lang = config.get("ocr_language") or "ara"
        self.extraction_pattern = config.get("extraction_pattern") or ""
        self.field_label = (
            config.get("designated_field_name")
            or config.get("license_field_name")
            or ""
        )

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        Parse the document at *file_path* and return a ParseResult.

        Args:
            file_path: Absolute path to a PDF or image file on the server.

        Returns:
            ParseResult
        """

    # ------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocess_for_ocr(image):
        """
        Prepare a PIL Image for Tesseract OCR.

        Steps:
          1. Convert to greyscale — colour information is irrelevant for text.
          2. Upsample if the image is narrower than ~1 800 px (below ~150 DPI
             equivalent for A4).  Minimum target is 300 DPI equivalent.
          3. Enhance contrast to sharpen faint characters.

        Returns a new greyscale PIL.Image.
        """
        from PIL import Image, ImageEnhance

        img = image.convert("L")  # greyscale

        # Upscale narrow images — OCR accuracy degrades below ~200 DPI.
        # We estimate DPI by assuming A4 width ≈ 2 480 px at 300 DPI.
        MIN_OCR_WIDTH = 1_800
        if img.width < MIN_OCR_WIDTH:
            scale = MIN_OCR_WIDTH / img.width
            img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.LANCZOS,
            )

        img = ImageEnhance.Contrast(img).enhance(1.8)
        return img

    @staticmethod
    def _file_to_images(file_path: str):
        """
        Render each page of a PDF (or load an image) as a PIL Image.

        Yields PIL.Image objects.
        """
        import fitz  # pymupdf
        from PIL import Image
        import io

        if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")):
            # Open then preprocess — image files have no guaranteed DPI so
            # OCR quality is poor without upsampling + contrast enhancement.
            raw = Image.open(file_path)
            yield BaseParser._preprocess_for_ocr(raw)
            return

        doc = fitz.open(file_path)
        for page in doc:
            pix = page.get_pixmap(dpi=300)  # 300 DPI for crisper OCR fallback
            yield Image.open(io.BytesIO(pix.tobytes("png")))
        doc.close()

    @staticmethod
    def _extract_qr_codes(image) -> list[str]:
        """
        Decode all QR / barcodes in a PIL Image.

        Returns a list of decoded string values.
        """
        from pyzbar.pyzbar import decode as pyzbar_decode

        results = []
        for obj in pyzbar_decode(image):
            try:
                results.append(obj.data.decode("utf-8"))
            except Exception:
                results.append(obj.data.decode("latin-1", errors="replace"))
        return results

    def _ocr_image(self, image) -> str:
        """
        Run Tesseract OCR on a PIL Image and return the text.

        Uses LSTM engine (--oem 1) which handles Arabic scripts more reliably
        than the legacy engine.  PSM 3 (auto page segmentation) is kept as
        the default so full-page layout analysis still runs.
        """
        import pytesseract

        config = "--oem 1 --psm 3"
        return pytesseract.image_to_string(image, lang=self.ocr_lang, config=config)

    def _apply_regex(self, text: str) -> str:
        """
        Apply self.extraction_pattern to *text* and return the first match group,
        or the full match if no groups, or "" if no match.
        """
        import re

        if not self.extraction_pattern:
            return ""
        m = re.search(self.extraction_pattern, text,
                      re.IGNORECASE | re.MULTILINE)
        if not m:
            return ""
        return m.group(1) if m.lastindex else m.group(0)

    @staticmethod
    def _build_display_html(raw_text: str, fields: dict, document_number: str) -> str:
        """Build a simple HTML snippet for the document_display Text Editor field."""
        rows = "".join(
            f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
            for k, v in fields.items()
        )
        table = f"<table border='1' cellpadding='4'>{rows}</table>" if rows else ""
        doc_num_line = (
            f"<p><strong>Document Number:</strong> {document_number}</p>"
            if document_number
            else ""
        )
        raw_block = (
            f"<details><summary>Raw Text</summary><pre>{raw_text}</pre></details>"
            if raw_text
            else ""
        )
        return f"{doc_num_line}{table}{raw_block}"
