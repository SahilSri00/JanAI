# document_pipeline.py
import os
import re
import unicodedata
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import structlog

log = structlog.get_logger()

# Tunables
CONFIDENCE_THRESHOLD = 0.7
MIN_TEXT_LENGTH = 10            # lower threshold — numeric IDs can be short
MIN_WORDS_FOR_FREE_TEXT = 3

# Map user language input to OCR engines' language codes
LANG_MAP = {
    "hi": "hi",
    "en": "en",
    "auto": "en",
}


def _upscale_image(file_path: str):
    img = cv2.imread(file_path)
    if img is None:
        return
    h, w = img.shape[:2]

    # Only upscale small images
    if max(h, w) < 1200:
        img = cv2.resize(
            img,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC
        )
        cv2.imwrite(file_path, img)


def _crop_top_half(file_path: str) -> Optional[str]:
    img = cv2.imread(file_path)
    if img is None:
        return None
    h, w = img.shape[:2]
    crop = img[0:int(h * 0.55), :]
    base, ext = os.path.splitext(file_path)
    temp_path = f"{base}_top{ext or '.png'}"
    cv2.imwrite(temp_path, crop)
    return temp_path


def extract_text(image_bytes: bytes,
                 filename: str = "document.jpg",
                 language: str = "hi") -> Dict:
    """
    High-level pipeline:
      1) OCR (language-aware single pass with fallback)
      2) Text cleanup
      3) Document classification (regex + keywords)
      4) Template-based structured extraction (OpenBharat only after classification)
      5) Field validation
      6) Confidence scoring

    Returns unified dict with keys:
      text, confidence (0-1), engine_used, blocks, doc_type, structured_fields,
      validated_fields, success, suggestions
    """
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        lang_code = LANG_MAP.get(language.lower(), "en")

        # 1) Preprocess: upscale small images for better small-font OCR
        _upscale_image(tmp_path)

        # 2) OCR (primary: PaddleOCR, fallback: EasyOCR)
        ocr_result = _run_ocr_with_fallback(tmp_path, lang_code)

        if not ocr_result or not ocr_result.get("text"):
            return {
                "text": "",
                "confidence": 0.0,
                "engine_used": "none",
                "blocks": [],
                "doc_type": "unknown",
                "structured_fields": {},
                "validated_fields": {},
                "success": False,
                "suggestions": [
                    "Upload a clearer image",
                    "Ensure text is not heavily skewed or occluded",
                ],
            }

        # 3) Text cleanup & normalization (preserves Unicode)
        cleaned = _clean_text_and_blocks(ocr_result["text"], ocr_result.get("blocks", []))
        text = cleaned["text"]
        blocks = cleaned["blocks"]
        avg_ocr_conf = ocr_result.get("confidence", 0.0)

        # 4) Document classification from text (regex + keywords)
        doc_type, doc_score, evidence = _classify_document(text)

        # 5) Template-based structured extraction (only for supported types)
        structured = {}
        structured_score = 0.0
        if doc_type in ("aadhaar", "pan", "voter", "passport", "driving"):
            structured = _run_template_extractor(tmp_path, doc_type)
            # structured is {} if extractor not available or failed
        # 6) Aadhaar-specific: crop upper 55% and re-run OCR to improve name / DOB extraction
        validation_text = text
        if doc_type == "aadhaar":
            top_path = None
            try:
                top_path = _crop_top_half(tmp_path)
                if top_path:
                    top_ocr = _run_ocr_with_fallback(top_path, lang_code)
                    top_text = (top_ocr or {}).get("text") or ""
                    if top_text.strip():
                        validation_text = top_text + "\n" + text
            except Exception:
                log.exception("aadhaar_top_half_ocr_failed")
            finally:
                if top_path:
                    try:
                        os.unlink(top_path)
                    except Exception:
                        log.debug("temp_top_crop_cleanup_failed", path=top_path)

        # 7) Field validation
        validated, validation_score = _validate_structured_fields(doc_type, structured, validation_text)

        # 8) Confidence scoring (unified)
        confidence = _compute_confidence(avg_ocr_conf, doc_score, validation_score, structured)

        success = bool(text and (confidence >= 0.0))  # we still return even for low confidence

        # suggestions for user if low confidence or missing key fields
        suggestions = []
        if confidence < CONFIDENCE_THRESHOLD:
            suggestions.append("Confidence low — consider reuploading a clearer image or higher resolution.")
        if doc_type == "aadhaar" and not validated.get("aadhaar_number"):
            suggestions.append("Could not reliably detect Aadhaar number. Ensure number is visible and not cropped.")

        return {
            "text": text,
            "confidence": round(confidence, 4),
            "engine_used": ocr_result.get("engine_used", "unknown"),
            "blocks": blocks,
            "doc_type": doc_type,
            "doc_evidence": evidence,
            "structured_fields": structured,
            "validated_fields": validated,
            "success": success,
            "suggestions": suggestions,
        }

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            log.exception("temp_file_cleanup_failed")


# -----------------------
# OCR (primary + fallback)
# -----------------------
def _run_ocr_with_fallback(file_path: str, lang_code: str) -> Dict:
    """
    Try PaddleOCR with requested language. If fails or very low output, try EasyOCR.
    Return canonicalized dict: {text, confidence, engine_used, blocks}
    """
    # try Paddle first
    result = _try_paddle(file_path, lang_code)
    if result and result.get("text"):
        # If paddle produced some text, return it (we allow fallback only on complete failure or extremely low conf)
        conf = result.get("confidence", 0.0)
        if conf >= 0.05 or len(result.get("text", "")) >= MIN_TEXT_LENGTH:
            return result
        log.warning("paddle.low_confidence_falling_back", confidence=conf)

    # fallback to EasyOCR
    easy = _try_easyocr(file_path, lang_code)
    if easy and easy.get("text"):
        return easy

    # return paddle result if easyocr didn't produce anything
    return result or easy or {"text": "", "confidence": 0.0, "engine_used": "none", "blocks": []}


def _try_paddle(file_path: str, lang_code: str) -> Dict:
    try:
        from paddleocr import PaddleOCR

        # PaddleOCR v3+ constructor
        paddle_kwargs = {
            "lang": lang_code,          # 'hi' or 'en'
            "device": "cpu",            # replaces use_gpu
            "enable_mkldnn": False,
            "cpu_threads": 2,
        }
        if lang_code == "hi":
            paddle_kwargs["text_recognition_model_name"] = "devanagari_PP-OCRv5_server_rec"

        ocr = PaddleOCR(**paddle_kwargs)

        # v3 no longer needs cls=True
        raw = ocr.ocr(file_path)

        if not raw:
            return {
                "text": "",
                "confidence": 0.0,
                "engine_used": "paddleocr",
                "blocks": []
            }

        blocks = []
        texts = []
        confidences = []

        # v3 returns: [[ [bbox], (text, confidence) ], ...]
        for page in raw:
            for item in page:
                try:
                    bbox = item[0]
                    text, conf = item[1]
                except Exception:
                    continue

                if not text or not text.strip():
                    continue

                conf = float(conf)
                if conf > 1:
                    conf = conf / 100.0

                conf = max(0.0, min(1.0, conf))

                blocks.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": bbox,
                    "engine": "paddleocr"
                })

                texts.append(text)
                confidences.append(conf)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": "\n".join(texts),
            "confidence": avg_conf,
            "engine_used": "paddleocr",
            "blocks": blocks
        }

    except Exception as e:
        log.exception("paddleocr.exception", error=str(e))
        return {
            "text": "",
            "confidence": 0.0,
            "engine_used": "paddleocr",
            "blocks": [],
            "error": str(e)
        }

def _try_easyocr(file_path: str, lang_code: str) -> Dict:
    try:
        import easyocr
        # prepare languages list for easyocr
        langs = []
        if lang_code == "hi":
            langs = ["hi", "en"]
        else:
            langs = [lang_code, "en"]
        if not hasattr(_try_easyocr, "reader"):
            log.info("easyocr.initializing", langs=langs)
            _try_easyocr.reader = easyocr.Reader(langs, gpu=False, model_storage_directory="./models", download_enabled=True)
        raw = _try_easyocr.reader.readtext(file_path)
        if not raw:
            return {"text": "", "confidence": 0.0, "engine_used": "easyocr", "blocks": []}
        blocks = []
        texts = []
        confs = []
        for item in raw:
            # item: (bbox, text, conf)
            try:
                bbox, text, conf = item
            except Exception:
                continue
            if not text or not text.strip():
                continue
            conf = float(conf)
            conf = max(0.0, min(1.0, conf))
            blocks.append({"text": text, "confidence": conf, "bbox": bbox, "engine": "easyocr"})
            texts.append(text)
            confs.append(conf)
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        # adjust easyocr small bias downward
        adjusted = avg_conf * 0.92
        return {"text": "\n".join(texts), "confidence": adjusted, "engine_used": "easyocr", "blocks": blocks}
    except Exception as e:
        log.exception("easyocr.exception", error=str(e))
        return {"text": "", "confidence": 0.0, "engine_used": "easyocr", "blocks": [], "error": str(e)}


# -----------------------
# Text cleanup & helpers
# -----------------------
def _clean_text_and_blocks(raw_text: str, blocks: List[Dict]) -> Dict:
    """
    Clean OCR raw lines:
     - preserve Unicode letters/digits
     - drop single-character garbage lines except digits (for ID numbers)
     - merge contiguous numeric-only lines into one (useful for Aadhaar 4-4-4 blocks)
     - normalize whitespace
    Returns cleaned dict {text, blocks}
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln is not None]
    cleaned_lines = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln:
            i += 1
            continue
        # If line is a single non-letter (trash) skip
        if _is_garbage_text(ln):
            i += 1
            continue
        # Merge numeric-only lines (digit groups) up to 3 consecutive for Aadhaar-like numbers
        if re.fullmatch(r"[\d\s\-]{2,}", ln):
            numeric_parts = [re.sub(r"[^\d]", "", ln)]
            j = i + 1
            while j < len(lines) and re.fullmatch(r"[\d\s\-]{1,}", lines[j]) and len(numeric_parts) < 3:
                numeric_parts.append(re.sub(r"[^\d]", "", lines[j]))
                j += 1
            merged = " ".join([p for p in numeric_parts if p])
            cleaned_lines.append(merged)
            i = j
            continue
        cleaned_lines.append(ln)
        i += 1

    # Post-process: remove accidental very short lines unless they contain digits or Devanagari letters
    final_lines = []
    for ln in cleaned_lines:
        if len(ln) <= 1 and not re.search(r"[\d\u0900-\u097F]", ln):
            continue
        final_lines.append(ln)

    # Normalize whitespace
    text = "\n".join(final_lines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()
    # blocks: attempt to filter original blocks similarly (best-effort)
    filtered_blocks = []
    for b in blocks:
        t = b.get("text", "").strip()
        if not t:
            continue
        if _is_garbage_text(t):
            continue
        filtered_blocks.append(b)
    return {"text": text, "blocks": filtered_blocks}


def _is_garbage_text(text: str) -> bool:
    """
    Unicode-aware garbage detector:
      - compute ratio of letter/number characters to total
      - detect long repeated-character sequences
    """
    if not text:
        return True
    text_len = len(text)
    if text_len == 0:
        return True

    valid_chars = 0
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("L") or cat.startswith("N"):
            valid_chars += 1
    ratio = valid_chars / text_len
    # repeated pattern
    if re.search(r"(.)\1{8,}", text):  # same char repeated 9+ times
        return True
    # if ascii punctuation-only (no letters/digits)
    if ratio < 0.3:
        # allow short digit-only strings (IDs)
        if re.fullmatch(r"[\d\s\-]{2,}", text):
            return False
        return True
    return False


# -----------------------
# Classification (regex + keywords)
# -----------------------
def _classify_document(text: str) -> Tuple[str, float, Dict]:
    """
    Return (doc_type, score, evidence)
    doc_type: 'aadhaar', 'pan', 'voter', 'passport', 'driving', 'unknown'
    score: 0-1
    evidence: dict listing matches
    """
    t_up = text  # don't uppercase Hindi; keep as-is
    score_map = {}
    evidence = {}

    # Aadhaar: strong 12-digit pattern
    aadhaar_m = re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", t_up)
    if aadhaar_m:
        score_map["aadhaar"] = score_map.get("aadhaar", 0.0) + 0.75
        evidence["aadhaar_number"] = aadhaar_m.group(0)

    if re.search(r"\b(आधार|UIDAI|आम आदमी का अधिकार)\b", t_up):
        score_map["aadhaar"] = score_map.get("aadhaar", 0.0) + 0.15
        evidence.setdefault("keywords", []).append("आधार/UIDAI")

    # PAN
    pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", t_up)
    if pan_m:
        score_map["pan"] = score_map.get("pan", 0.0) + 0.85
        evidence["pan_number"] = pan_m.group(0)

    if re.search(r"\b(INCOME TAX DEPARTMENT|Permanent Account Number|PAN)\b", t_up, flags=re.I):
        score_map["pan"] = score_map.get("pan", 0.0) + 0.1
        evidence.setdefault("keywords", []).append("PAN keywords")

    # Voter ID (EPIC)
    epic_m = re.search(r"\b([A-Z]{3}\d{7})\b", t_up)
    if epic_m:
        score_map["voter"] = score_map.get("voter", 0.0) + 0.7
        evidence["epic"] = epic_m.group(0)

    if re.search(r"\b(Election Commission|मतदाता|EPIC|Voter)\b", t_up, flags=re.I):
        score_map["voter"] = score_map.get("voter", 0.0) + 0.15
        evidence.setdefault("keywords", []).append("Voter keywords")

    # Passport (passport number often alphanumeric 7-8 chars)
    passport_m = re.search(r"\b([A-Z][0-9]{7})\b", t_up)
    if passport_m:
        score_map["passport"] = score_map.get("passport", 0.0) + 0.6
        evidence["passport_no"] = passport_m.group(0)

    if re.search(r"\b(PASSPORT|Passport)\b", t_up):
        score_map["passport"] = score_map.get("passport", 0.0) + 0.2
        evidence.setdefault("keywords", []).append("Passport keyword")

    # Driving licence (varies by state; look for DL or "Driving Licence")
    if re.search(r"\b(DRIVING LICENCE|DL No|Driving Licence|DL)\b", t_up, flags=re.I):
        score_map["driving"] = score_map.get("driving", 0.0) + 0.3
        evidence.setdefault("keywords", []).append("Driving keywords")

    if not score_map:
        return "unknown", 0.0, {}

    # choose best by max score
    best = max(score_map.items(), key=lambda x: x[1])
    # clamp score to 1.0
    doc_type = best[0]
    score = min(1.0, best[1])
    return doc_type, score, evidence


# -----------------------
# Template extractor (OpenBharat) - run only after classification
# -----------------------
def _run_template_extractor(file_path: str, doc_type: str) -> Dict:
    """
    Call OpenBharat extractor only for the given doc_type.
    Map doc_type (aadhaar -> front/back ambiguity) to the most likely function.
    Returns structured_fields dict (may be empty).
    """
    try:
        import openbharatocr
    except Exception as e:
        log.debug("openbharat.missing", error=str(e))
        return {}

    mapping = {
        "aadhaar": ["front_aadhaar", "back_aadhaar"],
        "pan": ["pan"],
        "voter": ["voter_id_front", "voter_id_back"],
        "passport": ["passport"],
        "driving": ["driving_licence"],
    }
    candidates = mapping.get(doc_type, [])
    results = {}
    for fn_name in candidates:
        try:
            func = getattr(openbharatocr, fn_name, None)
            if not func:
                continue
            raw = func(file_path)
            if raw and isinstance(raw, dict) and any(raw.values()):
                # prefer richer result (more keys)
                if len(raw.keys()) > len(results.keys()):
                    results = raw
        except Exception as e:
            log.debug("openbharat.extract_failed", fn=fn_name, error=str(e))
            continue
    return results or {}


# -----------------------
# Validation & scoring
# -----------------------
def _validate_structured_fields(doc_type: str, structured: Dict, free_text: str) -> Tuple[Dict, float]:
    """
    Validate fields found by template extractor and also attempt regex extraction from free_text
    Returns (validated_fields, validation_score 0-1)
    """
    validated = {}
    score_components = []
    # Aadhaar
    if doc_type == "aadhaar":
        # find aadhaar in structured or free_text
        aad = None
        if structured:
            for k, v in structured.items():
                if isinstance(v, str) and re.search(r"\d{4}\s*\d{4}\s*\d{4}", v):
                    aad = re.search(r"\d{4}\s*\d{4}\s*\d{4}", v).group(0)
                    break
        if not aad:
            m = re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", free_text)
            if m:
                aad = m.group(0)
        if aad:
            aad_norm = re.sub(r"\s+", " ", aad).strip()
            validated["aadhaar_number"] = aad_norm
            score_components.append(1.0)
        else:
            score_components.append(0.0)

        # name
        name = structured.get("name") or structured.get("full_name")
        if name and _looks_like_name(name):
            validated["name"] = name
            score_components.append(0.6)
        else:
            # try heuristic: first non-numeric, non-keyword line
            alt = _extract_name_from_free_text(free_text)
            if alt:
                validated["name"] = alt
                score_components.append(0.5)
            else:
                score_components.append(0.0)

        # dob
        dob = structured.get("dob") or structured.get("date_of_birth")
        if not dob:
            m = re.search(r"\b(\d{2}/\d{2}/\d{4}|\d{4})\b", free_text)
            dob = m.group(0) if m else None
        if dob and _validate_dob(dob):
            validated["dob"] = dob
            score_components.append(0.6)
        else:
            score_components.append(0.0)

    # PAN
    if doc_type == "pan":
        pan = structured.get("pan_number") or structured.get("pan")
        if not pan:
            m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", free_text)
            pan = m.group(0) if m else None
        if pan and _validate_pan(pan):
            validated["pan_number"] = pan
            score_components.append(1.0)
        else:
            score_components.append(0.0)

        # name
        name = structured.get("name")
        if name and _looks_like_name(name):
            validated["name"] = name
            score_components.append(0.6)
        else:
            score_components.append(0.0)

    # Voter / Passport / Driving basic checks: look for expected IDs
    if doc_type == "voter":
        epic = structured.get("epic_number")
        if not epic:
            m = re.search(r"\b([A-Z]{3}\d{7})\b", free_text)
            epic = m.group(0) if m else None
        if epic:
            validated["epic"] = epic
            score_components.append(0.9)
        else:
            score_components.append(0.0)

    if doc_type == "passport":
        pno = structured.get("passport_number") or re.search(r"\b([A-Z][0-9]{7})\b", free_text)
        if isinstance(pno, re.Match):
            pno = pno.group(0)
        if pno:
            validated["passport_number"] = pno
            score_components.append(0.8)
        else:
            score_components.append(0.0)

    if doc_type == "driving":
        dl = structured.get("dl_number")
        if not dl:
            m = re.search(r"\b([A-Z0-9\-\/]{6,})\b", free_text)
            dl = m.group(0) if m else None
        if dl:
            validated["dl_number"] = dl
            score_components.append(0.6)
        else:
            score_components.append(0.0)

    # If no specific doc_type (unknown) try to at least check for strong identifiers
    if doc_type == "unknown":
        # try to find pan/aadhaar as strong signal
        found_any = 0
        if re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", free_text):
            validated["aadhaar_number"] = re.search(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b", free_text).group(0)
            found_any += 1
            score_components.append(0.8)
        if re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", free_text):
            validated["pan_number"] = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", free_text).group(0)
            found_any += 1
            score_components.append(0.8)
        if found_any == 0:
            score_components.append(0.0)

    # final validation score - average of components (if none, return 0)
    validation_score = sum(score_components) / len(score_components) if score_components else 0.0
    return validated, max(0.0, min(1.0, validation_score))


# -----------------------
# Utility validators & extractors
# -----------------------
def _validate_pan(pan: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan.strip().upper()))


def _validate_dob(dob: str) -> bool:
    dob = dob.strip()
    if re.fullmatch(r"\d{4}", dob):
        year = int(dob)
        return 1900 <= year <= 2100
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", dob):
        d, m, y = dob.split("/")
        try:
            dd, mm, yy = int(d), int(m), int(y)
        except Exception:
            return False
        return 1900 <= yy <= 2100 and 1 <= mm <= 12 and 1 <= dd <= 31
    return False


def _looks_like_name(s: str) -> bool:
    s = s.strip()
    # name heuristic: contains letters (including Devanagari), not mostly digits, length reasonable
    letters = sum(1 for ch in s if unicodedata.category(ch).startswith("L"))
    digits = sum(1 for ch in s if unicodedata.category(ch).startswith("N"))
    if letters < 1:
        return False
    if digits / max(1, len(s)) > 0.3:
        return False
    if len(s) < 2:
        return False
    return True


def _extract_name_from_free_text(text: str) -> Optional[str]:
    # heuristics: pick first long line that is not a keyword and contains letters
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    keywords = {"आधार", "UIDAI", "INCOME", "TAX", "GOVT", "GOVERNMENT", "PAN", "EPIC", "DATE", "DOB"}
    for ln in lines:
        if len(ln) < 3:
            continue
        up = ln.upper()
        if any(k in up for k in keywords):
            continue
        if _looks_like_name(ln):
            return ln
    return None


def _compute_confidence(ocr_conf: float, doc_score: float, validation_score: float, structured: Dict) -> float:
    """
    Weighted combination:
      - ocr_conf: 50%
      - doc_score (classification from regex/keywords): 20%
      - validation_score (field validations): 25%
      - structured presence bonus: 5%
    """
    ocr_conf = float(ocr_conf or 0.0)
    doc_score = float(doc_score or 0.0)
    validation_score = float(validation_score or 0.0)
    structured_bonus = 0.05 if structured else 0.0
    combined = 0.5 * ocr_conf + 0.2 * doc_score + 0.25 * validation_score + structured_bonus
    # clamp
    return max(0.0, min(1.0, combined))

















# # 3 TIER MODEL

# import structlog
# import os
# from pathlib import Path
# import tempfile
# from typing import Dict, List, Optional
# import numpy as np

# # CRITICAL: Set BEFORE any paddle import
# os.environ['FLAGS_use_mkldnn'] = '0'
# os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

# log = structlog.get_logger()

# CONFIDENCE_THRESHOLD = 0.7
# MIN_TEXT_LENGTH = 20  # Reject if less than 20 chars


# def extract_text(image_bytes: bytes, filename: str = "document.jpg", 
#                  doc_hint: Optional[str] = None) -> Dict:
#     """
#     3-tier OCR cascade: OpenBharat → PaddleOCR → EasyOCR
    
#     Args:
#         image_bytes: Raw image bytes
#         filename: Original filename (for extension)
#         doc_hint: 'aadhaar', 'pan', 'passport', 'voter', 'driving', 'generic'
    
#     Returns:
#         {
#             "text": str,
#             "confidence": float,  # 0-1
#             "engine_used": str,
#             "blocks": List[dict],
#             "success": bool,
#             "fallback_chain": List[str]  # Which engines were tried
#         }
#     """
#     suffix = Path(filename).suffix or ".jpg"
    
#     with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
#         tmp.write(image_bytes)
#         tmp_path = tmp.name

#     fallback_chain = []
    
#     try:
#         # ========== TIER 1: OpenBharatOCR ==========
#         log.info("ocr.tier1_start", engine="openbharatocr", hint=doc_hint)
#         fallback_chain.append("openbharatocr")
        
#         result = _try_openbharat(tmp_path, doc_hint)
        
#         if _is_valid_result(result):
#             log.info("ocr.tier1_success", 
#                     confidence=result["confidence"],
#                     text_length=len(result["text"]))
#             result["success"] = True
#             result["fallback_chain"] = fallback_chain
#             return result
        
#         log.warning("ocr.tier1_failed", 
#                    reason=_failure_reason(result),
#                    confidence=result.get("confidence", 0))

#         # ========== TIER 2: PaddleOCR (Safe Mode) ==========
#         log.info("ocr.tier2_start", engine="paddleocr")
#         fallback_chain.append("paddleocr")
        
#         result = _try_paddle_safe(tmp_path)
        
#         if _is_valid_result(result):
#             log.info("ocr.tier2_success",
#                     confidence=result["confidence"],
#                     text_length=len(result["text"]))
#             result["success"] = True
#             result["fallback_chain"] = fallback_chain
#             return result
        
#         log.warning("ocr.tier2_failed",
#                    reason=_failure_reason(result),
#                    error=result.get("error"))

#         # ========== TIER 3: EasyOCR (Last Resort) ==========
#         log.info("ocr.tier3_start", engine="easyocr")
#         fallback_chain.append("easyocr")
        
#         result = _try_easyocr(tmp_path)
        
#         if _is_valid_result(result):
#             log.info("ocr.tier3_success",
#                     confidence=result["confidence"],
#                     text_length=len(result["text"]))
#             result["success"] = True
#             result["fallback_chain"] = fallback_chain
#             return result
        
#         log.error("ocr.total_failure", 
#                  fallback_chain=fallback_chain,
#                  last_error=result.get("error"))

#         # Return failure but with metadata
#         return {
#             "text": "",
#             "confidence": 0.0,
#             "engine_used": "none",
#             "blocks": [],
#             "success": False,
#             "fallback_chain": fallback_chain,
#             "error": "All OCR engines failed. Please upload a clearer image.",
#             "suggestions": [
#                 "Ensure good lighting (avoid shadows)",
#                 "Keep camera steady and parallel to document",
#                 "Make sure all text is clearly visible",
#                 "Try with a white background"
#             ]
#         }

#     finally:
#         try:
#             os.unlink(tmp_path)
#         except Exception as e:
#             log.warning("temp_file_cleanup_failed", error=str(e))


# def _is_valid_result(result: Dict) -> bool:
#     """Validate OCR result quality"""
#     if not result or not result.get("text"):
#         return False
    
#     text = result["text"].strip()
#     confidence = result.get("confidence", 0)
    
#     checks = [
#         len(text) >= MIN_TEXT_LENGTH,           # Minimum content
#         confidence >= 0.3,                         # Not completely garbage
#         len(text.split()) >= 3,                   # At least 3 words
#         not _is_garbage_text(text)                # Not random characters
#     ]
    
#     return all(checks)


# def _is_garbage_text(text: str) -> bool:
#     """Detect garbage OCR output"""
#     if not text:
#         return True
    
#     # Check for excessive non-alphanumeric characters
#     import re
#     alphanumeric_ratio = len(re.sub(r'[^a-zA-Z0-9\s]', '', text)) / len(text)
    
#     # Check for repeated characters (common OCR artifact)
#     repeated_pattern = re.search(r'(.)\1{10,}', text)  # Same char 10+ times
    
#     return alphanumeric_ratio < 0.5 or repeated_pattern is not None


# def _failure_reason(result: Dict) -> str:
#     """Human-readable failure reason"""
#     if not result or not result.get("text"):
#         return "no_text_extracted"
#     if len(result.get("text", "")) < MIN_TEXT_LENGTH:
#         return "text_too_short"
#     if result.get("confidence", 0) < 0.3:
#         return "low_confidence"
#     return "unknown"

# def _try_openbharat(file_path: str, doc_hint: Optional[str] = None) -> Dict:
#     """
#     Try all OpenBharatOCR document types
#     """
#     import openbharatocr
    
#     # CORRECT: Functions are at package level, not in submodules
#     doc_types = {
#         'aadhaar_front': openbharatocr.front_aadhaar,
#         'aadhaar_back': openbharatocr.back_aadhaar,
#         'pan': openbharatocr.pan,
#         'passport': openbharatocr.passport,
#         'voter_front': openbharatocr.voter_id_front,
#         'voter_back': openbharatocr.voter_id_back,
#         'driving': openbharatocr.driving_licence,
#         'birth_certificate': openbharatocr.birth_certificate,
#         'degree': openbharatocr.degree,
#         'vehicle': openbharatocr.vehicle_registration,
#         'water_bill': openbharatocr.water_bill,
#     }
    
#     # Map generic hints to specific functions
#     hint_mapping = {
#         'aadhaar': ['aadhaar_front', 'aadhaar_back'],
#         'voter': ['voter_front', 'voter_back'],
#     }
    
#     # If hint provided, try mapped functions first
#     if doc_hint in hint_mapping:
#         for specific_hint in hint_mapping[doc_hint]:
#             if specific_hint in doc_types:
#                 try:
#                     log.debug("openbharat.trying_hint", hint=specific_hint)
#                     raw = doc_types[specific_hint](file_path)
#                     result = _normalize_openbharat_result(raw, specific_hint)
#                     if _is_valid_result(result):
#                         return result
#                 except Exception as e:
#                     log.warning("openbharat.hint_failed", hint=specific_hint, error=str(e))
    
#     # Try all document types, pick best result
#     all_results = []
#     for doc_type, func in doc_types.items():
#         try:
#             log.debug("openbharat.trying", doc_type=doc_type)
#             raw = func(file_path)
#             result = _normalize_openbharat_result(raw, doc_type)
#             if _is_valid_result(result):
#                 all_results.append((result, len(result["text"]), result["confidence"]))
#                 log.info("openbharat.success", doc_type=doc_type, text_length=len(result["text"]))
#             else:
#                 log.debug("openbharat.invalid_result", doc_type=doc_type)
#         except Exception as e:
#             log.debug("openbharat.type_failed", type=doc_type, error=str(e))
#             continue
    
#     if all_results:
#         # Pick result with highest (text_length * confidence) score
#         best = max(all_results, key=lambda x: x[1] * x[2])[0]
#         log.info("openbharat.best_selected", 
#                 doc_type=best.get("doc_type"),
#                 text_length=len(best["text"]),
#                 confidence=best["confidence"])
#         return best
    
#     # No valid results from any type
#     log.warning("openbharat.no_valid_results", tried=list(doc_types.keys()))
#     return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr", "blocks": []}

# def _normalize_openbharat_result(raw: Dict, doc_type: str) -> Dict:
#     """
#     Normalize OpenBharatOCR output to standard format
#     """
#     if not raw or not isinstance(raw, dict):
#         return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr", "blocks": []}
    
#     # Extract all text fields into readable format
#     all_text = []
#     blocks = []
    
#     for field_name, field_value in raw.items():
#         if field_value and isinstance(field_value, str) and field_value.strip():
#             all_text.append(f"{field_name}: {field_value}")
#             blocks.append({
#                 "field": field_name,
#                 "text": field_value,
#                 "confidence": 0.9,  # OpenBharat doesn't give confidence, estimate high
#                 "type": doc_type
#             })
#         elif field_value and isinstance(field_value, list):
#             # Handle list values (e.g., multiple dates)
#             for item in field_value:
#                 if item and str(item).strip():
#                     all_text.append(f"{field_name}: {item}")
#                     blocks.append({
#                         "field": field_name,
#                         "text": str(item),
#                         "confidence": 0.85,
#                         "type": doc_type
#                     })
    
#     # Calculate pseudo-confidence based on field coverage
#     # More fields extracted = higher confidence
#     expected_fields = {
#         'aadhaar_front': ['name', 'aadhaar_number', 'dob', 'gender'],
#         'aadhaar_back': ['address', 'fathers_name'],
#         'pan': ['name', 'pan_number', 'dob', 'fathers_name'],
#         'passport': ['name', 'passport_number', 'nationality', 'dob'],
#         'voter_front': ['name', 'epic_number', 'dob', 'fathers_name'],
#         'voter_back': ['address'],
#         'driving': ['name', 'dl_number', 'address', 'validity_dates'],
#     }
    
#     if doc_type in expected_fields:
#         required = expected_fields[doc_type]
#         found = sum(1 for f in required if raw.get(f))
#         confidence = 0.5 + (0.5 * found / len(required))  # 0.5 to 1.0
#     else:
#         confidence = 0.7 if all_text else 0.0
    
#     return {
#         "text": "\n".join(all_text),
#         "confidence": confidence,
#         "engine_used": "openbharatocr",
#         "blocks": blocks,
#         "structured_fields": raw,
#         "doc_type": doc_type
#     }
    
    
# def _try_paddle_safe(file_path: str) -> Dict:
#     """
#     PaddleOCR with crash prevention
#     """
#     try:
#         from paddleocr import PaddleOCR
        
#         # Initialize fresh instance each time (slower but safer)
#         ocr = PaddleOCR(
#             use_angle_cls=True,
#             lang='en',  # Use 'hi' for Hindi-focused, 'ch' for Chinese
#             use_gpu=False,
#             enable_mkldnn=False,  # CRITICAL: Prevents your crash
#             cpu_threads=2,  # Limit threads for stability
#             show_log=False,
#             use_dilation=True,  # Better for text close to edges
#             det_db_score_mode='fast'  # Speed/accuracy balance
#         )
        
#         result = ocr.ocr(file_path, cls=True)
        
#         if not result or not result[0]:
#             return {"text": "", "confidence": 0.0, "engine_used": "paddleocr", "blocks": []}
        
#         lines = result[0]
#         blocks = []
#         all_text = []
#         confidences = []
        
#         for line in lines:
#             bbox, (text, conf) = line[0], line[1]
#             if text and text.strip():
#                 blocks.append({
#                     "text": text,
#                     "confidence": float(conf) / 100,  # Normalize to 0-1
#                     "bbox": bbox,
#                     "engine": "paddleocr"
#                 })
#                 all_text.append(text)
#                 confidences.append(float(conf) / 100)
        
#         avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
#         return {
#             "text": "\n".join(all_text),
#             "confidence": avg_confidence,
#             "engine_used": "paddleocr",
#             "blocks": blocks
#         }
        
#     except Exception as e:
#         log.error("paddleocr.exception", error=str(e), error_type=type(e).__name__)
#         return {
#             "text": "", 
#             "confidence": 0.0, 
#             "engine_used": "paddleocr",
#             "blocks": [],
#             "error": str(e)
#         }


# def _try_easyocr(file_path: str) -> Dict:
#     """
#     EasyOCR as last resort — initialize once if possible
#     """
#     try:
#         import easyocr
        
#         # Use class-level cache to avoid reloading model every time
#         if not hasattr(_try_easyocr, 'reader'):
#             log.info("easyocr.initializing")
#             _try_easyocr.reader = easyocr.Reader(
#                 ['en', 'hi'],  # English + Hindi
#                 gpu=False,
#                 model_storage_directory='./models',
#                 download_enabled=True
#             )
        
#         raw = _try_easyocr.reader.readtext(file_path)
        
#         if not raw:
#             return {"text": "", "confidence": 0.0, "engine_used": "easyocr", "blocks": []}
        
#         blocks = []
#         all_text = []
#         confidences = []
        
#         for (bbox, text, conf) in raw:
#             if text and text.strip():
#                 blocks.append({
#                     "text": text,
#                     "confidence": float(conf),
#                     "bbox": str(bbox),
#                     "engine": "easyocr"
#                 })
#                 all_text.append(text)
#                 confidences.append(float(conf))
        
#         avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
#         # EasyOCR confidence is often inflated, adjust down
#         adjusted_confidence = avg_confidence * 0.9
        
#         return {
#             "text": "\n".join(all_text),
#             "confidence": adjusted_confidence,
#             "engine_used": "easyocr",
#             "blocks": blocks
#         }
        
#     except Exception as e:
#         log.error("easyocr.exception", error=str(e))
#         return {
#             "text": "", 
#             "confidence": 0.0, 
#             "engine_used": "easyocr",
#             "blocks": [],
#             "error": str(e)
#         }









# working but just 2 tier 

# import structlog
# from openbharatocr import ocr as bharat_ocr
# from pathlib import Path
# import tempfile, os

# log = structlog.get_logger()

# CONFIDENCE_THRESHOLD = 0.7


# def extract_text(image_bytes: bytes, filename: str = "document.jpg") -> dict:
#     """
#     Primary OCR using OpenBharatOCR.
#     Falls back to PaddleOCR if confidence < threshold.
    
#     Returns:
#         {
#             "text": str,
#             "confidence": float,
#             "engine_used": str,
#             "blocks": list
#         }
#     """
#     # Write bytes to temp file (OpenBharatOCR needs file path)
#     suffix = Path(filename).suffix or ".jpg"
#     with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
#         tmp.write(image_bytes)
#         tmp_path = tmp.name

#     try:
#         log.info("ocr.start", engine="openbharatocr", file=filename)
#         result = _run_openbharat(tmp_path)

#         if result["confidence"] >= CONFIDENCE_THRESHOLD:
#             log.info("ocr.complete", engine="openbharatocr",
#                      confidence=result["confidence"])
#             return result

#         # Confidence too low — try PaddleOCR
#         log.warning("ocr.low_confidence", confidence=result["confidence"],
#                     threshold=CONFIDENCE_THRESHOLD, fallback="paddleocr")
#         paddle_result = _run_paddle(tmp_path)

#         # Return whichever got higher confidence
#         if paddle_result["confidence"] > result["confidence"]:
#             log.info("ocr.fallback_better", engine="paddleocr",
#                      confidence=paddle_result["confidence"])
#             return paddle_result

#         return result

#     finally:
#         os.unlink(tmp_path)  # Always clean up temp file


# def _run_openbharat(file_path: str) -> dict:
#     """Run OpenBharatOCR and normalize output."""
#     try:
#         from openbharatocr.ocr import aadhaar, pan, passport
#         from PIL import Image
        
#         # Try PAN card extraction first
#         try:
#             raw = pan(file_path)
#         except:
#             raw = {}

#         all_text = []
#         blocks = []
#         for field_name, field_value in raw.items():
#             if field_value and isinstance(field_value, str) and field_value.strip():
#                 all_text.append(f"{field_name}: {field_value}")
#                 blocks.append({
#                     "field": field_name,
#                     "text": field_value,
#                     "confidence": 0.9
#                 })

#         if not blocks:
#             # Fall through to PaddleOCR
#             return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr",
#                     "blocks": [], "structured_fields": {}}

#         return {
#             "text": "\n".join(all_text),
#             "confidence": 0.9,
#             "engine_used": "openbharatocr",
#             "blocks": blocks,
#             "structured_fields": raw
#         }

#     except Exception as e:
#         log.error("ocr.openbharat_failed", error=str(e))
#         return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr",
#                 "blocks": [], "error": str(e)}

# def _run_paddle(file_path: str) -> dict:
#     """Fallback OCR using EasyOCR (replacing PaddleOCR due to compatibility issues)."""
#     try:
#         import easyocr
#         reader = easyocr.Reader(['en', 'hi'], gpu=False)
#         raw = reader.readtext(file_path)

#         blocks = []
#         all_text = []
#         total_confidence = 0.0

#         for (bbox, text, conf) in raw:
#             if text.strip():
#                 blocks.append({
#                     "text": text,
#                     "confidence": float(conf),
#                     "bbox": str(bbox)
#                 })
#                 all_text.append(text)
#                 total_confidence += float(conf)

#         avg_confidence = total_confidence / len(blocks) if blocks else 0.0

#         return {
#             "text": "\n".join(all_text),
#             "confidence": avg_confidence,
#             "engine_used": "easyocr",
#             "blocks": blocks
#         }

#     except Exception as e:
#         log.error("ocr.easyocr_failed", error=str(e))
#         return {"text": "", "confidence": 0.0, "engine_used": "easyocr",
#                 "blocks": [], "error": str(e)}
        
        
        

# def _run_paddle(file_path: str) -> dict:
#     """Run PaddleOCR and normalize output."""
#     try:
#         # Disable PIR (Parallel Intermediate Representation) to avoid
#         # Unimplemented errors with PaddlePaddle 3.x
#         import paddle
#         paddle.set_flags({'FLAGS_enable_pir_api': False, 'FLAGS_enable_pir_in_executor': False})
        
#         from paddleocr import PaddleOCR
#         paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
#         raw = paddle_ocr.predict(file_path)
        
#         blocks = []
#         all_text = []
#         total_confidence = 0.0

#         if raw:
#             for result in raw:
#                 # PaddleOCR 3.x returns result differently
#                 rec_texts = result.get('rec_texts', [])
#                 rec_scores = result.get('rec_scores', [])
                
#                 for text, conf in zip(rec_texts, rec_scores):
#                     if text.strip():
#                         blocks.append({
#                             "text": text,
#                             "confidence": float(conf),
#                         })
#                         all_text.append(text)
#                         total_confidence += float(conf)

#         avg_confidence = total_confidence / len(blocks) if blocks else 0.0

#         return {
#             "text": "\n".join(all_text),
#             "confidence": avg_confidence,
#             "engine_used": "paddleocr",
#             "blocks": blocks
#         }

#     except Exception as e:
#         log.error("ocr.paddle_failed", error=str(e))
#         return {"text": "", "confidence": 0.0, "engine_used": "paddleocr",
#                 "blocks": [], "error": str(e)}