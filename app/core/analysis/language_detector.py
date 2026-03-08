from langdetect import detect, detect_langs, LangDetectException
from typing import List, Dict, Any


# Map langdetect codes to our language names
LANG_CODE_MAP = {
    "hi": "Hindi",
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "or": "Odia",
    "as": "Assamese",
    "sa": "Sanskrit",
}

# Minimum text length to attempt detection
MIN_CHARS = 20


def detect_language(text: str) -> Dict[str, Any]:
    """
    Detect the primary language of a text block.
    Returns language code, name, and confidence.
    """
    if not text or len(text.strip()) < MIN_CHARS:
        return {
            "language_code": "unknown",
            "language_name": "Unknown",
            "confidence": 0.0,
        }

    try:
        langs = detect_langs(text)
        if not langs:
            return {
                "language_code": "unknown",
                "language_name": "Unknown",
                "confidence": 0.0,
            }

        top = langs[0]
        code = top.lang
        confidence = round(top.prob, 2)

        return {
            "language_code": code,
            "language_name": LANG_CODE_MAP.get(code, code.upper()),
            "confidence": confidence,
        }

    except LangDetectException:
        return {
            "language_code": "unknown",
            "language_name": "Unknown",
            "confidence": 0.0,
        }


def detect_language_per_block(blocks: List[Dict]) -> List[Dict]:
    """
    Detect language for each OCR text block.
    Adds 'language' field to each block.

    blocks: list of dicts with at least a 'text' key.
    """
    enriched = []
    for block in blocks:
        text = block.get("text", "")
        lang_info = detect_language(text)
        enriched_block = {**block, "language": lang_info}
        enriched.append(enriched_block)
    return enriched


def detect_document_language(ocr_text: str) -> Dict[str, Any]:
    """
    Detect the overall document language from full OCR text.
    Also returns top 3 detected languages for mixed documents.
    """
    if not ocr_text or len(ocr_text.strip()) < MIN_CHARS:
        return {
            "primary_language": "unknown",
            "primary_language_name": "Unknown",
            "confidence": 0.0,
            "is_multilingual": False,
            "detected_languages": [],
        }

    try:
        langs = detect_langs(ocr_text)

        top = langs[0]
        primary_code = top.lang
        primary_conf = round(top.prob, 2)

        # Consider multilingual if second language has > 20% probability
        is_multilingual = len(langs) > 1 and langs[1].prob > 0.20

        detected = [
            {
                "language_code": l.lang,
                "language_name": LANG_CODE_MAP.get(l.lang, l.lang.upper()),
                "probability": round(l.prob, 2),
            }
            for l in langs[:3]
        ]

        return {
            "primary_language": primary_code,
            "primary_language_name": LANG_CODE_MAP.get(
                primary_code, primary_code.upper()
            ),
            "confidence": primary_conf,
            "is_multilingual": is_multilingual,
            "detected_languages": detected,
        }

    except LangDetectException:
        return {
            "primary_language": "unknown",
            "primary_language_name": "Unknown",
            "confidence": 0.0,
            "is_multilingual": False,
            "detected_languages": [],
        }
