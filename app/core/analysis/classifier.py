import re
from typing import Dict, Tuple
from app.core.analysis.fuzzy_matcher import fuzzy_boost_classification
from app.core.analysis.indic_bert import classify_with_indic_bert

# Simple keyword-based rules for schemes
SCHEME_KEYWORDS: Dict[str, Dict[str, list[str]]] = {
    "pm-kisan": {
        "must": [
            r"pradhan\s+mantri\s+kisan\s+samman\s+nidhi",
            r"pm[-\s]?kisan",
            r"kisan\s+samman",
        ],
        "boost": [
            r"small\s+and\s+marginal\s+landholding",
            r"farmer\s+families",
            r"2\s*ha\s+of\s+cultivable\s+land",
            r"khasra",
            r"land\s+record",
            r"agricultural\s+land",
            r"cultivable",
        ],
    },
    "ayushman-bharat": {
        "must": [
            r"ayushman\s+bharat",
            r"pradhan\s+mantri\s+jan\s+arogya",
            r"pmjay",
        ],
        "boost": [
            r"golden\s+card",
            r"health\s+insurance",
            r"sehat",
            r"hospitalization",
            r"empanelled\s+hospital",
            r"secondary\s+and\s+tertiary\s+care",
        ],
    },
    "ration-card": {
        "must": [
            r"ration\s+card",
            r"nfsa",
            r"national\s+food\s+security",
        ],
        "boost": [
            r"antyodaya",
            r"priority\s+household",
            r"fair\s+price\s+shop",
            r"below\s+poverty\s+line",
            r"bpl",
            r"apl",
            r"food\s+grain",
        ],
    },
    "aadhaar-services": {
        "must": [
            r"uidai",
            r"aadhaar",
            r"unique\s+identification",
        ],
        "boost": [
            r"enrolment\s+form",
            r"correction\s+form",
            r"update\s+aadhaar",
            r"biometric",
            r"demographic\s+update",
            r"aadhaar\s+card\s+correction",
        ],
    },
    "social-pension": {
        "must": [
            r"old\s+age\s+pension",
            r"widow\s+pension",
            r"disability\s+pension",
            r"social\s+pension",
            r"nsap",
        ],
        "boost": [
            r"indira\s+gandhi\s+national",
            r"ignoaps",
            r"ignwps",
            r"igndps",
            r"senior\s+citizen",
            r"divyang",
            r"handicapped",
            r"monthly\s+pension",
        ],
    },
    "pan-card": {
        "must": [
            r"permanent\s+account\s+number",
            r"form\s+49a",
            r"pan\s+card",
        ],
        "boost": [
            r"income\s+tax\s+department",
            r"pan\s+application",
            r"nsdl",
            r"utiitsl",
            r"tin\s+facilitation",
            r"tax\s+payer",
        ],
    },
}

DOCUMENT_TYPE_RULES = {
    "APPLICATION_FORM": [
        r"application\s+form",
        r"registration\s+form",
        r"form\s+no\.",
        r"application\s+for",
        r"apply\s+for",
        r"enrollment\s+form",
        r"please\s+fill",
        r"to\s+be\s+filled",
    ],
    "REJECTION_NOTICE": [
        r"rejection\s+order",
        r"not\s+eligible",
        r"your\s+application\s+has\s+been\s+rejected",
        r"regret\s+to\s+inform",
        r"application\s+rejected",
        r"ineligible",
        r"disqualified",
    ],
    "APPROVAL_LETTER": [
        r"sanction\s+order",
        r"hereby\s+sanctioned",
        r"application\s+approved",
        r"congratulations",
        r"has\s+been\s+approved",
        r"beneficiary\s+approved",
    ],
    "NOTICE": [
        r"notice\s+to",
        r"public\s+notice",
        r"office\s+order",
        r"circular\s+no",
        r"government\s+of\s+india\s+notification",
    ],
}

def classify_document(ocr_text: str) -> Dict:
    """
    Classify document using three-layer approach:
    1. Keyword matching (fast, rule-based)
    2. Fuzzy matching (handles typos)
    3. Indic-BERT (semantic, handles paraphrasing)

    Final result combines all three for best accuracy.
    """
    text = ocr_text.lower()

    # --- Layer 1: Document type via keywords ---
    doc_type_scores: Dict[str, int] = {}
    for doc_type, patterns in DOCUMENT_TYPE_RULES.items():
        score = 0
        for pat in patterns:
            if re.search(pat, text):
                score += 1
        doc_type_scores[doc_type] = score

    best_doc_type = "APPLICATION_FORM"
    if doc_type_scores:
        best_doc_type = max(doc_type_scores, key=doc_type_scores.get)
        if doc_type_scores[best_doc_type] == 0:
            best_doc_type = "APPLICATION_FORM"

    # --- Layer 2: Scheme via keywords ---
    scheme_scores: Dict[str, int] = {}
    for scheme_id, cfg in SCHEME_KEYWORDS.items():
        must_patterns = cfg.get("must", [])
        boost_patterns = cfg.get("boost", [])

        if not any(re.search(pat, text) for pat in must_patterns):
            scheme_scores[scheme_id] = 0
            continue

        score = 0
        for pat in must_patterns:
            if re.search(pat, text):
                score += 2
        for pat in boost_patterns:
            if re.search(pat, text):
                score += 1
        scheme_scores[scheme_id] = score

    best_scheme = "unknown"
    best_score = 0
    for sid, sc in scheme_scores.items():
        if sc > best_score:
            best_scheme = sid
            best_score = sc

    confidence = 0.0
    if best_scheme != "unknown":
        cfg = SCHEME_KEYWORDS[best_scheme]
        max_score = (
            2 * len(cfg.get("must", [])) + len(cfg.get("boost", []))
        )
        confidence = round(best_score / max_score, 2) if max_score > 0 else 0.0

    # --- Layer 3: Fuzzy boost ---
    boosted = fuzzy_boost_classification(
        ocr_text=ocr_text,
        keyword_scheme_id=best_scheme,
        keyword_confidence=confidence,
    )

    # --- Layer 4: Indic-BERT (when confidence still low) ---
    bert_result = None
    if boosted["confidence"] < 0.6:
        bert_result = classify_with_indic_bert(ocr_text)

        # If Indic-BERT is more confident, use it
        if (
            bert_result["scheme_id"] != "unknown"
            and bert_result["confidence"] > boosted["confidence"]
        ):
            boosted["scheme_id"] = bert_result["scheme_id"]
            boosted["confidence"] = bert_result["confidence"]
            boosted["method"] = "indic-bert"
            best_doc_type = bert_result["document_type"]

    return {
        "document_type": best_doc_type,
        "scheme_id": boosted["scheme_id"],
        "confidence": boosted["confidence"],
        "detection_method": boosted.get("method", "keyword"),
        "all_scores": scheme_scores,
        "bert_result": bert_result,
    }
