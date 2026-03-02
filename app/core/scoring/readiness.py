SCHEME_REQUIREMENTS = {
    "pm-kisan": {
        "required_fields": [
            "applicant_name", "father_name", "aadhaar_number",
            "bank_account", "ifsc_code", "mobile_number",
            "khasra_number", "land_area"
        ],
        "required_documents": [
            "land_records", "aadhaar_card", "bank_passbook"
        ]
    },
    "ayushman-bharat": {
        "required_fields": [
            "applicant_name", "aadhaar_number", "mobile_number",
            "family_members", "income_level"
        ],
        "required_documents": [
            "aadhaar_card", "ration_card", "income_certificate"
        ]
    },
    "ration-card": {
        "required_fields": [
            "applicant_name", "father_name", "address",
            "family_members", "mobile_number"
        ],
        "required_documents": [
            "aadhaar_card", "address_proof", "passport_photo"
        ]
    },
    "aadhaar-services": {
        "required_fields": [
            "aadhaar_number", "applicant_name", "date_of_birth",
            "mobile_number", "correction_field"
        ],
        "required_documents": [
            "identity_proof", "address_proof"
        ]
    },
    "social-pension": {
        "required_fields": [
            "applicant_name", "date_of_birth", "aadhaar_number",
            "bank_account", "ifsc_code", "pension_type"
        ],
        "required_documents": [
            "aadhaar_card", "age_proof", "bank_passbook",
            "income_certificate"
        ]
    },
    "pan-card": {
        "required_fields": [
            "applicant_name", "father_name", "date_of_birth",
            "aadhaar_number", "mobile_number"
        ],
        "required_documents": [
            "identity_proof", "address_proof", "passport_photo"
        ]
    },
    "unknown": {
        "required_fields": [],
        "required_documents": []
    }
}

# Regex patterns to detect fields in OCR text
import re

FIELD_PATTERNS = {
    "applicant_name":  r"(name|नाम)\s*[:\-]?\s*([A-Za-z\u0900-\u097F\s]{3,40})",
    "father_name":     r"(father|पिता|s/o|son of)\s*[:\-]?\s*([A-Za-z\u0900-\u097F\s]{3,40})",
    "date_of_birth":   r"(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})",
    "aadhaar_number":  r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "pan_number":      r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "mobile_number":   r"\b[6-9]\d{9}\b",
    "bank_account":    r"\b\d{9,18}\b",
    "ifsc_code":       r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "pincode":         r"\b\d{6}\b",
    "khasra_number":   r"(khasra|खसरा)\s*[:\-]?\s*(\d{1,8})",
    "land_area":       r"(area|क्षेत्रफल|hectare|हेक्टेयर)\s*[:\-]?\s*([\d\.]+)",
}


def extract_fields_from_text(ocr_text: str) -> dict:
    """Detect which fields are present in OCR text using regex."""
    found = {}
    for field_id, pattern in FIELD_PATTERNS.items():
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            found[field_id] = {
                "found": True,
                "value": match.group(0)[:50]  # cap length
            }
    return found


def calculate_readiness_score(ocr_text: str, scheme_id: str, uploaded_docs: list = None) -> dict:
    """
    Score = (fields_complete * 0.60) + (docs_present * 0.30) + (validation * 0.10)
    """
    uploaded_docs = uploaded_docs or []
    requirements = SCHEME_REQUIREMENTS.get(scheme_id, SCHEME_REQUIREMENTS["unknown"])

    required_fields = requirements["required_fields"]
    required_docs = requirements["required_documents"]

    # Component 1 — fields (60%)
    found_fields = extract_fields_from_text(ocr_text)
    completed_fields = [f for f in required_fields if f in found_fields]
    field_score = len(completed_fields) / len(required_fields) if required_fields else 1.0

    # Component 2 — documents (30%)
    present_docs = [d for d in required_docs if d in uploaded_docs]
    doc_score = len(present_docs) / len(required_docs) if required_docs else 0.0

    # Component 3 — validation (10%)
    # Basic: check known patterns pass validation
    validation_checks = []
    if "aadhaar_number" in found_fields:
        val = found_fields["aadhaar_number"]["value"].replace(" ", "")
        validation_checks.append(len(val) == 12 and val.isdigit())
    if "pan_number" in found_fields:
        val = found_fields["pan_number"]["value"]
        validation_checks.append(bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', val)))
    if "mobile_number" in found_fields:
        val = found_fields["mobile_number"]["value"]
        validation_checks.append(bool(re.match(r'^[6-9]\d{9}$', val)))

    val_score = (sum(validation_checks) / len(validation_checks)) if validation_checks else 0.5

    # Final weighted score
    raw = (field_score * 0.60) + (doc_score * 0.30) + (val_score * 0.10)
    final_score = round(raw * 100)

    # Risk level
    if final_score >= 90:
        risk = "LOW"
    elif final_score >= 70:
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    # Missing items
    missing_fields = [f for f in required_fields if f not in found_fields]
    missing_docs = [d for d in required_docs if d not in uploaded_docs]

    return {
        "score": final_score,
        "risk_level": risk,
        "components": {
            "fields": round(field_score * 60),
            "documents": round(doc_score * 30),
            "validation": round(val_score * 10),
            "fields_detail": f"{len(completed_fields)}/{len(required_fields)} fields found",
            "docs_detail": f"{len(present_docs)}/{len(required_docs)} documents uploaded"
        },
        "missing_fields": missing_fields,
        "missing_documents": missing_docs,
        "found_fields": found_fields
    }