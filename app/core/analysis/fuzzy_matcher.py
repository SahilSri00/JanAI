from rapidfuzz import fuzz, process
from typing import Optional

# Scheme name variants people commonly write
SCHEME_ALIASES = {
    "pm-kisan": [
        "pm kisan",
        "pradhan mantri kisan samman nidhi",
        "pm kisaan",
        "kisan samman nidhi",
        "pmkisan",
        "p.m. kisan",
        "pradhanmantri kisan",
        "किसान सम्मान निधि",
        "पीएम किसान",
    ],
    "ayushman-bharat": [
        "ayushman bharat",
        "ayushman bharat pmjay",
        "pradhan mantri jan arogya yojana",
        "pmjay",
        "ayushman card",
        "golden card",
        "आयुष्मान भारत",
        "जन आरोग्य योजना",
    ],
    "ration-card": [
        "ration card",
        "rashon card",
        "nfsa",
        "national food security",
        "bpl card",
        "apl card",
        "राशन कार्ड",
        "सार्वजनिक वितरण",
    ],
    "aadhaar-services": [
        "aadhaar",
        "aadhar",
        "adhar",
        "uidai",
        "unique identification",
        "aadhaar correction",
        "aadhaar update",
        "आधार",
        "यूआईडीएआई",
    ],
    "social-pension": [
        "old age pension",
        "widow pension",
        "disability pension",
        "divyang pension",
        "nsap",
        "indira gandhi pension",
        "वृद्धावस्था पेंशन",
        "विधवा पेंशन",
        "विकलांगता पेंशन",
    ],
    "pan-card": [
        "pan card",
        "permanent account number",
        "pan application",
        "form 49a",
        "nsdl pan",
        "utiitsl",
        "पैन कार्ड",
    ],
}

# Flatten all aliases with their scheme_id for fast lookup
_ALL_ALIASES = []
for scheme_id, aliases in SCHEME_ALIASES.items():
    for alias in aliases:
        _ALL_ALIASES.append((alias.lower(), scheme_id))


def fuzzy_match_scheme(ocr_text: str, threshold: int = 75) -> Optional[str]:
    """
    Use fuzzy matching to identify scheme from OCR text.
    Returns scheme_id if a match above threshold is found, else None.

    threshold: 0-100, higher = stricter matching.
    """
    text = ocr_text.lower()

    best_scheme = None
    best_score = 0

    for alias, scheme_id in _ALL_ALIASES:
        # Use partial_ratio for substring matching
        # (alias may appear as part of longer text)
        score = fuzz.partial_ratio(alias, text)
        if score > best_score:
            best_score = score
            best_scheme = scheme_id

    if best_score >= threshold:
        return best_scheme
    return None


def fuzzy_boost_classification(
    ocr_text: str,
    keyword_scheme_id: str,
    keyword_confidence: float,
) -> dict:
    """
    Combine keyword classification with fuzzy matching.
    If keyword confidence is low, try fuzzy matching to confirm or override.

    Returns updated classification dict.
    """
    # If keyword confidence is already high, trust it
    if keyword_confidence >= 0.7:
        return {
            "scheme_id": keyword_scheme_id,
            "confidence": keyword_confidence,
            "method": "keyword",
        }

    # Low confidence — try fuzzy matching
    fuzzy_scheme = fuzzy_match_scheme(ocr_text)

    if fuzzy_scheme and fuzzy_scheme != "unknown":
        # Fuzzy found something
        if fuzzy_scheme == keyword_scheme_id:
            # Both agree — boost confidence
            boosted_confidence = min(keyword_confidence + 0.2, 0.95)
            return {
                "scheme_id": fuzzy_scheme,
                "confidence": boosted_confidence,
                "method": "keyword+fuzzy",
            }
        else:
            # Fuzzy disagrees — use fuzzy result with moderate confidence
            return {
                "scheme_id": fuzzy_scheme,
                "confidence": 0.6,
                "method": "fuzzy_override",
            }

    # Fuzzy found nothing either — return keyword result as-is
    return {
        "scheme_id": keyword_scheme_id,
        "confidence": keyword_confidence,
        "method": "keyword",
    }
