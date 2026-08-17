# Copyright (c) 2026, QualityPoint and contributors
# For license information, please see license.txt

"""
Generic document parser — works for any country / document type.

Supports three strategies driven by parser_type:
  - "QR"    : scan for QR/barcodes; first decoded value = document_number
  - "OCR"   : OCR all pages; apply extraction_pattern regex to get document_number
  - "Regex" : same as OCR (the distinction is only meaningful for config display)
"""

from naqel.utils.document_parser.base_parser import BaseParser, ParseResult


class GenericParser(BaseParser):
    """Country-agnostic parser using pyzbar and/or pytesseract."""

    def parse(self, file_path: str) -> ParseResult:
        result = ParseResult()

        try:
            images = list(self._file_to_images(file_path))
        except Exception as exc:
            result.error = f"Could not render document: {exc}"
            return result

        parser_type: str = (self.config.get("parser_type") or "OCR").strip()

        if parser_type == "QR":
            return self._parse_qr(images, result)

        # OCR or Regex
        return self._parse_ocr(file_path, images, result)

    # ------------------------------------------------------------------

    def _parse_qr(self, images, result: ParseResult) -> ParseResult:
        all_qr: list[str] = []
        for img in images:
            all_qr.extend(self._extract_qr_codes(img))

        if all_qr:
            result.raw_text = "\n".join(all_qr)
            result.document_number = all_qr[0]
            result.fields = {f"QR {i+1}": v for i, v in enumerate(all_qr)}
            result.display_html = self._build_display_html(
                result.raw_text, result.fields, result.document_number
            )
            result.success = True
        else:
            result.error = "No QR or barcode found in the document."

        return result

    def _parse_ocr(self, file_path: str, images, result: ParseResult) -> ParseResult:
        import re

        # Pick the pattern matching the configured language.
        # Arabic (ara) → use extraction_pattern_ar if provided, else fall back
        # to extraction_pattern. Any other language → always use extraction_pattern.
        ocr_lang = self.ocr_lang or "ara"
        is_arabic = ocr_lang.startswith("ara")
        pattern_ar = self.config.get("extraction_pattern_ar") or ""
        pattern_en = self.extraction_pattern or ""
        pattern = (pattern_ar or pattern_en) if is_arabic else (
            pattern_en or pattern_ar)

        has_named_pattern = bool(
            self.config.get("raw_text_only")
            and pattern
            and self._has_named_groups(pattern)
        )

        # For address documents on digital PDFs, fitz text extraction gives
        # clean readable text. Fall back to Tesseract only for scanned PDFs.
        raw_text = ""
        if self.config.get("raw_text_only") and file_path.lower().endswith(".pdf"):
            raw_text = self._extract_pdf_text(file_path)

        if not raw_text:
            # Named-group patterns contain both _ar and _en groups, so we need
            # clean Arabic text AND clean English text.
            #
            # Running the full image through a single ara+eng pass causes
            # Tesseract to confuse the two columns on bilingual side-by-side
            # certificates (e.g. SPL National Address Proof): Arabic OCR reads
            # the English column and produces Arabic-character garbage, while
            # English OCR reads the Arabic column and similarly fails.
            #
            # Solution — column split before OCR:
            #   Right half  → Arabic OCR   (Arabic is always on the right)
            #   Left half   → English OCR  (English is always on the left)
            # This feeds each engine only its own script and eliminates
            # cross-column contamination entirely.
            if has_named_pattern:
                import pytesseract
                ar_parts, en_parts = [], []
                for img in images:
                    preprocessed = self._preprocess_for_ocr(img)
                    w, h = preprocessed.size
                    # The SPL National Address Proof has digit cells in the
                    # CENTER of the page (~35-65% width).  A strict 50/50 split
                    # cuts right through those cells, leaving bracket/digit
                    # artifacts at the crop boundary that contaminate adjacent
                    # text captures.
                    #
                    # Use a 40/60 overlap instead:
                    #   Arabic OCR — rightmost 60%:  fully includes digit cells
                    #                                + Arabic text columns
                    #   English OCR — leftmost 60%:  fully includes digit cells
                    #                                + English text columns
                    #
                    # PSM 3 (auto page segmentation) is used instead of PSM 6
                    # because each crop still contains a two-region layout
                    # (digit column + text column) that PSM 3 handles better.
                    ar_start = int(w * 0.40)  # Arabic: right 60%
                    en_end   = int(w * 0.60)  # English: left 60%
                    ar_crop = preprocessed.crop((ar_start, 0, w, h))
                    en_crop = preprocessed.crop((0, 0, en_end, h))
                    try:
                        ar_parts.append(pytesseract.image_to_string(
                            ar_crop, lang="ara", config="--oem 1 --psm 3"))
                    except Exception:
                        ar_parts.append("")
                    try:
                        en_parts.append(pytesseract.image_to_string(
                            en_crop, lang="eng", config="--oem 1 --psm 3"))
                    except Exception:
                        en_parts.append("")
                raw_text = "\n".join(ar_parts) + "\n" + "\n".join(en_parts)
            else:
                raw_parts = []
                for img in images:
                    raw_parts.append(self._ocr_image(img))
                raw_text = "\n".join(raw_parts)

        result.raw_text = raw_text

        # --- Branch 1: named-group pattern → structured field extraction ----
        # Works for any document type (Saudi address proof, trade licence, …).
        # Group names become field labels; digit-per-line values are collapsed.
        # Raw text is always forwarded so that parse_sample_document can show
        # it in a <details> block when show_raw_text_in_display is on — and,
        # crucially, when the pattern matches nothing the user still sees the
        # OCR output and can debug their extraction pattern.
        if self.config.get("raw_text_only") and pattern and self._has_named_groups(pattern):
            extracted = self._extract_named_groups(pattern, raw_text)
            ocr_lang = self.config.get("ocr_language") or "ara"
            result.fields = self._filter_by_language(extracted, ocr_lang)
            result.document_number = ""
            result.success = True
            if not result.fields:
                result.warnings.append(
                    "Extraction pattern did not match any fields in the document. "
                    "Check the pattern against the raw text shown below."
                )
            result.display_html = self._build_display_html(
                raw_text, result.fields, result.document_number
            )
            return result

        # --- Branch 2: no pattern → raw text only (address, no identifier) --
        if self.config.get("raw_text_only"):
            result.document_number = ""
            result.fields = {}
            result.success = True
            targeted = self.config.get("targeted_fields") or []
            hint = ""
            if targeted:
                labels = ", ".join(f"<strong>{f}</strong>" for f in targeted)
                hint = f"<p><em>Fields that will be populated:</em> {labels}</p>"
            result.display_html = hint + self._build_display_html(
                raw_text, result.fields, result.document_number
            )
            return result

        # --- Branch 3: single-value extraction (credentials / licence) ------
        doc_number = self._apply_regex(raw_text)
        result.document_number = doc_number

        if doc_number:
            label = self.field_label or "Extracted Value"
            result.fields = {label: doc_number}
            result.success = True
        else:
            result.fields = {}
            result.success = False
            result.error = (
                "OCR succeeded but the extraction pattern returned no match."
                if pattern
                else "No extraction_pattern configured — cannot extract document number."
            )

        result.display_html = self._build_display_html(
            raw_text, result.fields, result.document_number
        )
        return result

    # ------------------------------------------------------------------
    # Named-group helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_by_language(groups: dict, ocr_lang: str) -> dict:
        """
        Filter named-group extraction results by language suffix.

        Convention:
          - Groups ending in _ar  → Arabic values
          - Groups ending in _en  → English values
          - Groups with no suffix → language-neutral (numbers, codes); always kept

        The suffix is stripped from the returned key so downstream field mapping
        works the same regardless of language (e.g. street_ar → street).

        Length-based fallback:
          Character-set ratio cannot distinguish valid script characters from
          garbled same-script OCR noise.  Instead, if the preferred-language
          value is suspiciously short (< 3 meaningful characters) compared to
          the available fallback (which has at least twice as many characters),
          the fallback is used.  This catches the common case of Arabic OCR
          producing a 1-2 character stub (e.g. \u0628\u0647 for a city name that
          should be 6+ chars) while English OCR produced the correct value.
        """
        want_ar = ocr_lang.startswith("ara")

        # Collect both language variants for every base key ------------------
        ar_vals: dict[str, str] = {}
        en_vals: dict[str, str] = {}
        neutral: dict[str, str] = {}

        for key, val in groups.items():
            if val is None:
                continue
            if key.endswith("_ar"):
                ar_vals[key[:-3]] = val
            elif key.endswith("_en"):
                en_vals[key[:-3]] = val
            else:
                neutral[key] = val

        result: dict[str, str] = {}

        # Language-neutral groups are always kept ----------------------------
        result.update(neutral)

        # For each base key that has at least one language variant -----------
        all_base_keys = set(ar_vals) | set(en_vals)

        def _meaningful_len(s: str) -> int:
            """Count non-space, non-punctuation characters."""
            return sum(1 for c in s if c.isalnum() or '\u0600' <= c <= '\u06ff')

        for base_key in all_base_keys:
            ar_val = ar_vals.get(base_key)
            en_val = en_vals.get(base_key)

            prefer_val  = ar_val if want_ar else en_val
            fallback_val = en_val if want_ar else ar_val

            if prefer_val is None:
                if fallback_val is not None:
                    result[base_key] = fallback_val
                continue

            # Length-based fallback: if the preferred value is very short and
            # the fallback is substantially longer, use the fallback.
            if fallback_val is not None:
                pref_len = _meaningful_len(prefer_val)
                fall_len = _meaningful_len(fallback_val)
                if pref_len < 3 and fall_len >= pref_len * 2:
                    result[base_key] = fallback_val
                    continue

            result[base_key] = prefer_val

        return result

    @staticmethod
    def _has_named_groups(pattern: str) -> bool:
        """Return True if *pattern* contains at least one named capture group."""
        import re
        return bool(re.search(r'\(\?P<\w+>', pattern))

    @staticmethod
    def _collapse_digits(value: str) -> str:
        """
        Collapse a digit-per-line, digit-per-space, pipe-separated, or
        bracket-bordered digit sequence into a single number.

        Handles all layouts produced by different extraction paths:
          - fitz (digital PDF):  "5\n2\n0\n3"   → "5203"  (newline-per-digit)
          - Tesseract plain:     "5 2 0 3"       → "5203"  (space-separated)
          - Tesseract table:     "| 6 | 5| 5| 2" → "6552"  (pipe-cell borders)
          - Tesseract table:     "[6][5][5][2]"  → "6552"  (bracket-cell borders)
          - Tesseract mixed:     "[2|6|1|4]"     → "2614"  (bracket + pipe)
        Non-digit sequences are returned stripped and unchanged.
        """
        import re
        # Primary: strip all cell-border separators (brackets/pipes/whitespace).
        # If ONLY digits remain the whole value is a cell-boxed number field.
        # Handles: "[2|614[5" → "26145", "[6][5][5][2]" → "6552", etc.
        digits_only = re.sub(r'[|\[\]\s]+', '', value)
        if digits_only and digits_only.isdigit():
            return digits_only
        # Newline-separated single digits (fitz PDF table-cell format)
        lines = [l.strip() for l in value.splitlines() if l.strip()]
        if lines and all(re.fullmatch(r'\d', l) for l in lines):
            return "".join(lines)
        # Space-separated single digits (plain OCR or after separator stripping)
        cleaned = re.sub(r'[|\[\]\s]+', ' ', value).strip()
        tokens = cleaned.split()
        if len(tokens) > 1 and all(re.fullmatch(r'\d', t) for t in tokens):
            return "".join(tokens)
        return value.strip()

    @classmethod
    def _extract_named_groups(cls, pattern: str, text: str) -> dict:
        """
        Apply *pattern* (DOTALL|MULTILINE|IGNORECASE) to *text*.
        Returns {group_name: value} for every named group that matched,
        with digit-per-line values collapsed into plain numbers and
        leading cell-border artifacts stripped from text values.

        If the full-pattern match does not capture all named groups (e.g.
        because the document field order differs from the pattern), each
        missing group is retried individually using the literal text
        immediately preceding it in the pattern as an anchor.
        """
        import re
        result = {}
        try:
            m = re.search(pattern, text, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if m:
                for name, value in m.groupdict().items():
                    if value is not None:
                        result[name] = cls._clean_captured_value(value)
        except re.error:
            pass

        # Partial-match fallback -------------------------------------------
        try:
            all_names = re.findall(r'\(\?P<(\w+)>', pattern)
            missing = [n for n in all_names if n not in result]
            if missing:
                split_re = re.compile(
                    r'(\(\?P<\w+>(?:[^()]+|\((?:[^()]+|\([^()]*\))*\))*\))'
                )
                tokens = split_re.split(pattern)
                for idx, token in enumerate(tokens):
                    gp_name_m = re.match(r'\(\?P<(\w+)>', token)
                    if not gp_name_m:
                        continue
                    name = gp_name_m.group(1)
                    if name not in missing:
                        continue
                    gap = tokens[idx - 1] if idx > 0 else ""
                    anchor = re.sub(r'^[\s\S]*\.\*\?', '', gap)
                    anchor = re.sub(r'^[\s\S]*\.\+\?', '', anchor)
                    anchor = anchor.lstrip()
                    if len(anchor) > 80:
                        tail = anchor[-120:]
                        paren_pos = tail.find('(')
                        anchor = tail[paren_pos:] if paren_pos != -1 else tail
                    sub_pattern = anchor + token
                    try:
                        sm = re.search(sub_pattern, text,
                                       re.DOTALL | re.MULTILINE | re.IGNORECASE)
                        if sm and sm.group(name) is not None:
                            result[name] = cls._clean_captured_value(sm.group(name))
                    except re.error:
                        pass
        except Exception:
            pass

        return result

    @classmethod
    def _clean_captured_value(cls, value: str) -> str:
        """
        Collapse digit sequences and strip OCR cell-border artifacts.

        Two-step process:
          1. Try _collapse_digits — converts digit-per-line/space/bracket
             sequences (e.g. "| 6 | 5| 5| 2" or "[6][5][5][2]") into
             a plain number string.
          2. For text fields (value contains letters/Arabic), strip any
             leading bracket/pipe/digit sequences that leaked from adjacent
             digit table cells during OCR (e.g. "]655 نوفل" → "نوفل",
             "[2|614[5] عيض" → "عيض").
        """
        import re
        collapsed = cls._collapse_digits(value)
        # If the collapsed value still contains non-digit characters it is a
        # text field — remove any leading cell-border noise.
        if any(c.isalpha() or '\u0600' <= c <= '\u06ff' for c in collapsed):
            cleaned = re.sub(r'^[\[\]|0-9\s]+', '', collapsed).strip()
            return cleaned if cleaned else collapsed
        return collapsed

    @staticmethod
    def _extract_pdf_text(file_path: str) -> str:
        """Extract embedded text from a PDF using PyMuPDF. Returns \"\" on failure."""
        try:
            import fitz
            doc = fitz.open(file_path)
            parts = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(parts).strip()
        except Exception:
            return ""
