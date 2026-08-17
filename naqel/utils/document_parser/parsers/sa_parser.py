# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

"""
Saudi Arabia document parser.

Strategy:
  1. Render each page of the PDF/image to a PIL Image.
  2. Scan every image for QR codes using pyzbar.
  3. If a QR code is found:
       a. If the QR value is an 8-char alphanumeric Saudi short address
          (e.g. "DMAA6552"), call the SPL National Address API to resolve
          the full address fields.
       b. If the QR value is a Saudi proof-of-address verification URL
          (proof.address.gov.sa), extract the ID parameter as the
          document number and display the verification link.
       c. Otherwise treat the QR value as the document_number directly.
  4. If no QR found, fall back to OCR + extraction_pattern (GenericParser).
"""

import re
from urllib.parse import parse_qs, urlparse

from naqel.utils.document_parser.base_parser import BaseParser, ParseResult


# Saudi short address: 4 alpha + 4 digits  (e.g. DMAA6552)
_SA_SHORT_ADDRESS_RE = re.compile(r"^[A-Z]{4}\d{4}$", re.IGNORECASE)

# Saudi proof-of-address verification URL  (proof.address.gov.sa/...)
_SPL_PROOF_URL_RE = re.compile(
    r"^https?://proof\.address\.gov\.sa/", re.IGNORECASE
)

# Loose pattern used to locate the short address in ara+eng OCR output.
# Each character may be surrounded by spaces, pipes, or dots (table cells).
# After stripping non-alphanumeric chars the 8-char result is validated.


class SAParser(BaseParser):
    """Parser for Saudi national address proof and similar documents."""

    def parse(self, file_path: str) -> ParseResult:
        result = ParseResult()

        try:
            images = list(self._file_to_images(file_path))
        except Exception as exc:
            result.error = f"Could not render document: {exc}"
            return result

        # --- Step 1: scan all pages for QR codes --------------------------
        qr_values: list[str] = []
        for img in images:
            qr_values.extend(self._extract_qr_codes(img))

        if qr_values:
            return self._handle_qr(qr_values[0], file_path, images, result)

        # --- Step 2: fallback — OCR + regex --------------------------------
        # When called from the national-address context (parse_national_address /
        # parse_sample_document), raw_text_only=True is set in the config.
        # In that case delegate to GenericParser's named-group OCR pipeline so
        # that address_extraction_pattern is honoured exactly as it would be
        # with "OCR Only" strategy.  This handles scanned SPL proofs or any
        # other Saudi document that contains no QR code.
        if self.config.get("raw_text_only"):
            from naqel.utils.document_parser.parsers.generic_parser import GenericParser
            ocr_delegate = GenericParser({**self.config, "parser_type": "OCR"})
            return ocr_delegate._parse_ocr(file_path, images, result)

        # Credential-parsing fallback: single-value extraction.
        raw_parts = []
        for img in images:
            raw_parts.append(self._ocr_image(img))
        result.raw_text = "\n".join(raw_parts)

        doc_number = self._apply_regex(result.raw_text)
        result.document_number = doc_number
        result.fields = {"Extracted Value": doc_number} if doc_number else {}
        result.display_html = self._build_display_html(
            result.raw_text, result.fields, result.document_number
        )
        result.success = bool(doc_number)
        if not doc_number:
            result.error = "No QR code found and regex extraction returned no match."
        return result

    # ------------------------------------------------------------------

    def _handle_qr(self, qr_value: str, file_path: str, images: list, result: ParseResult) -> ParseResult:
        result.raw_text = qr_value

        if _SA_SHORT_ADDRESS_RE.match(qr_value.strip()):
            # It's a Saudi short address code — return it directly as document_number
            return self._lookup_short_address(qr_value.strip(), result)

        if _SPL_PROOF_URL_RE.match(qr_value.strip()):
            # It's a Saudi proof-of-address verification URL.
            return self._handle_proof_url(qr_value.strip(), file_path, images, result)

        # Generic QR value (URL, number, etc.) — treat as document_number
        result.document_number = qr_value
        result.fields = {"QR Value": qr_value}
        result.display_html = self._build_display_html(
            "", result.fields, qr_value)
        result.success = True
        return result

    def _handle_proof_url(self, url: str, file_path: str, images: list, result: ParseResult) -> ParseResult:
        """
        Handle a Saudi proof-of-address verification URL.

        The QR encodes a URL like:
            https://proof.address.gov.sa/verifyproofna.aspx?type=c&ID=...&doc=...

        The Short Address (e.g. JCMA5203) is NOT in the QR.  Strategy:
          1. Use PyMuPDF (fitz) to extract embedded text directly from the PDF
             — no OCR, no font confusion.  SPL PDFs have the short address as
             selectable text, so this is reliable and fast.
          2. Fall back to ara+eng OCR if fitz extraction finds nothing
             (e.g. scanned image PDFs).
          3. If still nothing, surface the URL metadata only.
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        doc_ref = (params.get("doc") or [""])[0]

        short_address = self._extract_short_address_from_pdf(file_path)

        if not short_address:
            # Fallback: ara+eng OCR
            import pytesseract
            bilingual_parts = []
            for img in images:
                try:
                    bilingual_parts.append(
                        pytesseract.image_to_string(img, lang="ara+eng")
                    )
                except Exception:
                    bilingual_parts.append(self._ocr_image(img))
            bilingual_text = "\n".join(bilingual_parts)
            result.raw_text = bilingual_text
            short_address = self._extract_short_address_from_text(
                bilingual_text)

        if short_address:
            result = self._lookup_short_address(short_address, result)
            if doc_ref:
                result.fields["Proof Number"] = doc_ref
            result.fields["Verification URL"] = (
                f'<a href="{url}" target="_blank">Verify</a>'
            )
            result.display_html = self._build_display_html(
                "", result.fields, result.document_number
            )
            return result

        # Fallback — short address not recoverable at all
        proof_id = (params.get("ID") or params.get("id") or [""])[0]
        result.document_number = proof_id or url
        result.fields = {
            "Proof Number": doc_ref,
            "Account ID": proof_id,
            "Verification URL": f'<a href="{url}" target="_blank">Verify</a>',
        }
        result.display_html = self._build_display_html(
            "", result.fields, result.document_number)
        result.success = True
        result.warnings.append(
            "Short address not found in document; address fields not populated."
        )
        return result

    @staticmethod
    def _extract_short_address_from_pdf(file_path: str) -> str:
        """
        Use PyMuPDF to extract embedded text from a PDF and search for a
        Saudi short address (4 letters + 4 digits).  This is the most
        reliable method because it reads the actual glyphs, not a rendered
        image, so Arabic/Latin confusion does not apply.

        Returns the first match (uppercased), or "".
        """
        if not file_path.lower().endswith(".pdf"):
            return ""
        try:
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                text = page.get_text()
                # Case 1: short address as a single token (e.g. "JCMA5203")
                for word in re.findall(r'[A-Z]{4}\d{4}', text, re.IGNORECASE):
                    if _SA_SHORT_ADDRESS_RE.match(word):
                        doc.close()
                        return word.upper()
                # Case 2: each character on its own line, as fitz reads SPL
                # table cells — "J\nC\nM\nA\n5\n2\n0\n3"
                m = re.search(
                    r'([A-Za-z])\n([A-Za-z])\n([A-Za-z])\n([A-Za-z])\n'
                    r'(\d)\n(\d)\n(\d)\n(\d)',
                    text,
                )
                if m:
                    candidate = "".join(m.groups()).upper()
                    if _SA_SHORT_ADDRESS_RE.match(candidate):
                        doc.close()
                        return candidate
            doc.close()
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_short_address_from_text(text: str) -> str:
        """
        Search plain OCR text for a Saudi short address.

        Case 1: clean 8-char token (e.g. ``JCMA5203`` on a single line).
        Case 2: each character on its own line — the same per-line table-cell
        layout that fitz produces in PDFs also appears in Tesseract output for
        scanned documents where the short address sits inside a narrow column.
        """
        # Case 1: single-token match
        for word in re.findall(r'[A-Z]{4}\d{4}', text, re.IGNORECASE):
            if _SA_SHORT_ADDRESS_RE.match(word):
                return word.upper()

        # Case 2: one character per line (OCR of table-cell short address)
        m = re.search(
            r'([A-Za-z])\n([A-Za-z])\n([A-Za-z])\n([A-Za-z])\n'
            r'(\d)\n(\d)\n(\d)\n(\d)',
            text,
        )
        if m:
            candidate = "".join(m.groups()).upper()
            if _SA_SHORT_ADDRESS_RE.match(candidate):
                return candidate

        return ""

    def _lookup_short_address(self, short_address: str, result: ParseResult) -> ParseResult:
        """Return a basic result for a short address code (API lookup removed)."""
        result.document_number = short_address
        result.fields = {"Short Address": short_address}
        result.display_html = self._build_display_html(
            short_address, result.fields, short_address
        )
        result.success = True
        return result

    @staticmethod
    def _flatten_address(addr: dict) -> dict:
        """Extract readable fields from the SPL address response dict."""
        mapping = {
            "ShortAddress": "Short Address",
            "BuildingNumber": "Building Number",
            "Street": "Street",
            "District": "District",
            "City": "City",
            "RegionName": "Region",
            "PostCode": "Post Code",
            "AdditionalNumber": "Additional Number",
        }
        return {label: addr[key] for key, label in mapping.items() if addr.get(key)}
