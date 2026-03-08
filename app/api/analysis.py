from fastapi import APIRouter, HTTPException
from app.core.translation.bhashini import translate
from app.db.mongo import get_documents_collection, get_db
from app.core.scoring.decision import generate_action_items
from app.core.analysis.deadline import extract_deadlines
from app.core.analysis.rejection import is_rejection_notice, extract_rejection_reasons
from app.core.analysis.language_detector import detect_document_language
from app.core.analysis.similarity import semantic_extract_rejection_reasons

router = APIRouter(tags=["analysis"])


def _get_progress_collection():
    db = get_db()
    return db["progress"]


@router.get("/analysis/{document_id}")
async def get_analysis(document_id: str):
    """
    Return full analysis for a document:
    - OCR result
    - classification
    - readiness score
    - quality info
    - action items
    - deadlines
    - rejection reasons
    - detected language
    """
    collection = get_documents_collection()
    doc = await collection.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document not found"},
        )

    ocr_result = doc.get("ocr_result", {})
    classification = doc.get("classification", {})
    score_result = doc.get("score_result", {})
    quality = doc.get("quality", {})
    language = doc.get("language", "hi")

    missing_fields = score_result.get("missing_fields", [])
    missing_documents = score_result.get("missing_documents", [])
    scheme_id = classification.get("scheme_id", "unknown")

    action_items = generate_action_items(
        scheme_id=scheme_id,
        missing_fields=missing_fields,
        missing_documents=missing_documents,
        language=language,
    )

    raw_ocr_text = ocr_result.get("text", "")

    # Extract deadlines from OCR text
    deadlines = extract_deadlines(raw_ocr_text)

    # Detect document language
    detected_language = detect_document_language(raw_ocr_text)

    # Rejection notice analysis
    rejection_reasons = []
    is_rejection = is_rejection_notice(raw_ocr_text)
    if is_rejection:
        # Semantic similarity first
        semantic_reasons = semantic_extract_rejection_reasons(raw_ocr_text)
        # Regex-based to fill gaps
        regex_reasons = extract_rejection_reasons(raw_ocr_text)
        seen_ids = {r["reason_id"] for r in semantic_reasons}
        for r in regex_reasons:
            if r["reason_id"] not in seen_ids:
                semantic_reasons.append(r)
                seen_ids.add(r["reason_id"])
        rejection_reasons = semantic_reasons

    # Fetch completed actions from progress collection
    progress_col = _get_progress_collection()
    progress_doc = await progress_col.find_one({"document_id": document_id})
    completed_actions = (
        progress_doc.get("completed_actions", []) if progress_doc else []
    )

    # Mark completed flag on each action item
    for item in action_items:
        item_id = item.get("action_id")
        item["completed"] = item_id in completed_actions

    return {
        "success": True,
        "data": {
            "document_id": doc["document_id"],
            "status": doc.get("status", "UNKNOWN"),
            "language": language,
            "detected_language": detected_language,
            "filename": doc.get("filename"),
            "ocr_result": ocr_result,
            "classification": classification,
            "score_result": score_result,
            "quality": quality,
            "action_items": action_items,
            "deadlines": deadlines,
            "is_rejection_notice": is_rejection,
            "rejection_reasons": rejection_reasons,
        },
    }


# ── Test endpoints ─────────────────────────────────────────────────────────────

@router.get("/deadline-test")
async def deadline_test():
    sample_text = """
    Last date to apply: 31/03/2026
    Camp verification date: 15 April 2026
    Date of Birth: 12/05/1985
    Submit your application before 20-04-2026
    """
    result = extract_deadlines(sample_text)
    return {"deadlines": result}


@router.get("/rejection-test")
async def rejection_test():
    sample_text = """
    REJECTION ORDER
    Your application has been rejected due to the following reasons:
    1. Aadhaar verification failed - name mismatch with bank records
    2. Land records invalid - khasra number not found in state database
    3. Bank account number incorrect - IFSC code invalid
    4. Document not attached - income certificate missing
    """
    is_rejection = is_rejection_notice(sample_text)
    reasons = extract_rejection_reasons(sample_text)
    return {"is_rejection_notice": is_rejection, "rejection_reasons": reasons}


@router.get("/fuzzy-test")
async def fuzzy_test():
    from app.core.analysis.fuzzy_matcher import fuzzy_match_scheme
    tests = [
        "PM KISAAN application form for farmers",
        "Ayushman Bhrat PMJAY golden card",
        "Rashon card nfsa below poverty",
        "Aadhar correction form uidai",
        "Old age pensoin widow divyang nsap",
        "PAN crad form 49A income tax",
    ]
    results = []
    for text in tests:
        matched = fuzzy_match_scheme(text)
        results.append({"text": text, "matched_scheme": matched})
    return {"results": results}


@router.get("/language-test")
async def language_test():
    tests = [
        "This is an application form for PM-KISAN scheme for farmers.",
        "यह आवेदन पत्र पीएम किसान योजना के लिए है। कृपया सभी विवरण भरें।",
        "இது PM-KISAN திட்டத்திற்கான விண்ணப்பம்.",
        "This form contains both English and हिंदी text mixed together.",
    ]
    results = []
    for text in tests:
        result = detect_document_language(text)
        results.append({"text": text[:50], "detection": result})
    return {"results": results}


@router.get("/similarity-test")
async def similarity_test():
    from app.core.analysis.similarity import find_similar_rejection_reasons
    tests = [
        "Your submission was not accepted as the form was left incomplete",
        "We could not verify your identity document as it has passed its expiry date",
        "The name on your bank account does not match the name on your Aadhaar card",
        "Your annual earnings are above the permissible limit for this welfare program",
        "A previous application from this Aadhaar number already exists in our system",
    ]
    results = []
    for text in tests:
        matches = find_similar_rejection_reasons(text)
        results.append({
            "input": text,
            "top_match": matches[0] if matches else None,
        })
    return {"results": results}


@router.get("/bert-test")
async def bert_test():
    from app.core.analysis.indic_bert import classify_with_indic_bert
    tests = [
        "Application for PM-KISAN Kisan Samman Nidhi farmer land khasra",
        "Ayushman Bharat health insurance hospital treatment BPL family",
        "Ration card food security fair price shop grain distribution",
        "Your application has been rejected you are not eligible",
        "आधार कार्ड सुधार फॉर्म UIDAI बायोमेट्रिक",
    ]
    results = []
    for text in tests:
        result = classify_with_indic_bert(text)
        results.append({"text": text[:50], "result": result})
    return {"results": results}
@router.get("/translate-test")
async def translate_test(
    text: str = "Hello farmer this is a sample message",
    src: str = "en",
    tgt: str = "hi",
):
    """
    Test Bhashini translation with Redis caching.
    First call hits Bhashini API.
    Second call with same params returns from Redis cache.
    """
    result = await translate(text=text, source_lang=src, target_lang=tgt)
    return {"success": True, "data": result}
