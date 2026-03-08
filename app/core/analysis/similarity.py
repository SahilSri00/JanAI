from sentence_transformers import SentenceTransformer, util
from typing import List, Dict, Any, Optional
import torch

# Use a small, fast model that works well on CPU
MODEL_NAME = "paraphrase-MiniLM-L6-v2"

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Lazy load model on first use."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


# Canonical rejection reason sentences
# These are the "ground truth" sentences we compare against
REJECTION_REASON_CORPUS = [
    {
        "reason_id": "incomplete_form",
        "canonical": "Application form has empty blank fields that were not filled by the applicant",
        "title": "Incomplete form",
        "remediation": "Fill all mandatory fields in the form completely before resubmitting.",
        "priority": 1,
    },
    {
        "reason_id": "invalid_aadhaar",
        "canonical": "Aadhaar card number is wrong invalid or Aadhaar biometric verification failed",
        "title": "Invalid or mismatched Aadhaar",
        "remediation": "Verify your Aadhaar number carefully. Ensure name and date of birth match Aadhaar exactly.",
        "priority": 1,
    },
    {
        "reason_id": "bank_details_mismatch",
        "canonical": "Bank account number IFSC code is wrong or bank details could not be verified",
        "title": "Invalid or mismatched bank details",
        "remediation": "Cross-check account number and IFSC from your bank passbook.",
        "priority": 1,
    },
    {
        "reason_id": "land_records_invalid",
        "canonical": "Land ownership records khasra khatauni could not be verified from revenue department",
        "title": "Land records invalid or not verified",
        "remediation": "Obtain updated land records from your tehsil office or state land portal.",
        "priority": 1,
    },
    {
        "reason_id": "not_eligible",
        "canonical": "Applicant does not qualify or is ineligible for this government welfare scheme",
        "title": "Eligibility criteria not met",
        "remediation": "Review the eligibility criteria carefully.",
        "priority": 1,
    },
    {
        "reason_id": "document_missing",
        "canonical": "Required supporting documents were not submitted or are missing from the application",
        "title": "Required document not attached",
        "remediation": "Attach all required supporting documents as per the scheme guidelines.",
        "priority": 1,
    },
    {
        "reason_id": "document_expired",
        "canonical": "Submitted document certificate has crossed its validity expiry date and is no longer valid",
        "title": "Document expired",
        "remediation": "Renew the expired document before reapplying.",
        "priority": 1,
    },
    {
        "reason_id": "duplicate_application",
        "canonical": "Another application was previously submitted with the same Aadhaar number already exists",
        "title": "Duplicate application",
        "remediation": "Check your application status online before submitting again.",
        "priority": 2,
    },
    {
        "reason_id": "name_mismatch",
        "canonical": "Name spelling is different across Aadhaar card bank passbook and application form documents",
        "title": "Name mismatch across documents",
        "remediation": "Ensure your name is spelled identically across all documents.",
        "priority": 2,
    },
    {
        "reason_id": "photo_mismatch",
        "canonical": "Passport photograph submitted is blurry unclear or does not match the applicant face",
        "title": "Photo mismatch or unclear",
        "remediation": "Submit a recent clear passport-size photograph.",
        "priority": 2,
    },
    {
        "reason_id": "income_limit_exceeded",
        "canonical": "Annual income salary earnings of applicant is above the maximum permitted income limit",
        "title": "Income exceeds scheme limit",
        "remediation": "This scheme has an income eligibility limit. Obtain an updated income certificate.",
        "priority": 2,
    },
    {
        "reason_id": "signature_missing",
        "canonical": "Applicant has not signed the application form signature is absent or missing",
        "title": "Signature missing",
        "remediation": "Sign the application form at all required places before resubmitting.",
        "priority": 2,
    },
    {
        "reason_id": "address_mismatch",
        "canonical": "Residential address written on form is different from address shown on address proof document",
        "title": "Address mismatch",
        "remediation": "Ensure address on the form matches your address proof document.",
        "priority": 2,
    },
]


# Pre-compute corpus embeddings at import time (lazy)
_corpus_embeddings = None


def _get_corpus_embeddings():
    """Compute and cache corpus embeddings."""
    global _corpus_embeddings
    if _corpus_embeddings is None:
        model = get_model()
        sentences = [r["canonical"] for r in REJECTION_REASON_CORPUS]
        _corpus_embeddings = model.encode(sentences, convert_to_tensor=True)
    return _corpus_embeddings


def find_similar_rejection_reasons(
    text: str,
    threshold: float = 0.40,   # lowered from 0.45
    top_k: int = 5,
) -> List[Dict[str, Any]]:

    """
    Find rejection reasons semantically similar to the input text.

    Uses sentence-transformers cosine similarity against
    canonical rejection reason sentences.

    threshold: minimum similarity score (0-1) to include a result.
    top_k: maximum number of reasons to return.
    """
    if not text or len(text.strip()) < 10:
        return []

    model = get_model()
    corpus_embeddings = _get_corpus_embeddings()

    # Encode input
    query_embedding = model.encode(text, convert_to_tensor=True)

    # Compute cosine similarity
    cosine_scores = util.cos_sim(query_embedding, corpus_embeddings)[0]

    # Get top matches above threshold
    scores = cosine_scores.tolist()
    results = []

    for idx, score in enumerate(scores):
        if score >= threshold:
            reason = REJECTION_REASON_CORPUS[idx]
            results.append({
                "reason_id": reason["reason_id"],
                "title": reason["title"],
                "remediation": reason["remediation"],
                "priority": reason["priority"],
                "similarity_score": round(score, 3),
                "action_id": f"rejection_{reason['reason_id']}",
            })

    # Sort by similarity score descending
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:top_k]


def semantic_extract_rejection_reasons(
    ocr_text: str,
    threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """
    Split OCR text into sentences and find rejection reasons
    semantically for each sentence.

    Combines results, deduplicates by reason_id,
    keeps highest similarity score per reason.
    """
    if not ocr_text:
        return []

    # Split into sentences
    sentences = [
        s.strip()
        for s in ocr_text.replace("\n", ". ").split(".")
        if len(s.strip()) > 15
    ]

    seen_reason_ids = {}

    for sentence in sentences:
        matches = find_similar_rejection_reasons(sentence, threshold=threshold)
        for match in matches:
            rid = match["reason_id"]
            if rid not in seen_reason_ids:
                seen_reason_ids[rid] = match
            else:
                # Keep highest similarity score
                if match["similarity_score"] > seen_reason_ids[rid]["similarity_score"]:
                    seen_reason_ids[rid] = match

    results = list(seen_reason_ids.values())
    results.sort(key=lambda x: (x["priority"], -x["similarity_score"]))
    return results
