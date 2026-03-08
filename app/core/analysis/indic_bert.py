import torch
from sentence_transformers import SentenceTransformer, util
from typing import Dict, Any, Optional
import structlog

log = structlog.get_logger()

# Multilingual model supporting Hindi + all Indian languages
# Already downloaded when you installed sentence-transformers
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("indic_bert.loading_model", model=MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        log.info("indic_bert.model_loaded")
    return _model


SCHEME_DESCRIPTIONS = {
    "pm-kisan": (
        "PM-KISAN farmer kisan agricultural land khasra khatauni "
        "crop cultivation small marginal farmer income support "
        "pradhan mantri kisan samman nidhi rupees per year "
        "किसान सम्मान निधि कृषि भूमि खसरा"
    ),
    "ayushman-bharat": (
        "Ayushman Bharat PMJAY health hospital medical treatment "
        "health insurance coverage BPL poor family golden card "
        "empanelled hospital cashless treatment five lakh "
        "आयुष्मान भारत स्वास्थ्य बीमा अस्पताल"
    ),
    "ration-card": (
        "ration card food grain wheat rice distribution "
        "fair price shop PDS public distribution system "
        "BPL APL antyodaya household food security NFSA "
        "राशन कार्ड अनाज वितरण उचित मूल्य दुकान"
    ),
    "aadhaar-services": (
        "Aadhaar UIDAI biometric fingerprint iris unique identification "
        "enrolment correction update demographic address name change "
        "twelve digit number identity document "
        "आधार बायोमेट्रिक सुधार नामांकन"
    ),
    "social-pension": (
        "pension monthly old age elderly widow widower disability "
        "divyang handicapped NSAP Indira Gandhi beneficiary "
        "senior citizen social security welfare payment "
        "वृद्धावस्था पेंशन विधवा विकलांग"
    ),
    "pan-card": (
        "PAN permanent account number income tax taxpayer "
        "Form 49A NSDL UTIITSL TIN financial transaction "
        "ten digit alphanumeric tax department "
        "पैन कार्ड आयकर विभाग"
    ),
    "unknown": (
        "miscellaneous general unrelated random document "
        "no specific government scheme"
    ),
}

DOCUMENT_TYPE_DESCRIPTIONS = {
    "APPLICATION_FORM": (
        "application form fill blank fields submit apply "
        "registration enrollment request form number "
        "please fill required information applicant details "
        "आवेदन पत्र भरें आवेदक विवरण"
    ),
    "REJECTION_NOTICE": (
        "rejected rejection refused not approved denied "
        "application rejected regret ineligible not eligible "
        "your application could not be accepted reason for rejection "
        "आवेदन अस्वीकार निरस्त अपात्र"
    ),
    "APPROVAL_LETTER": (
        "approved sanctioned congratulations accepted confirmed "
        "beneficiary approved your application has been approved "
        "sanction order hereby granted "
        "स्वीकृत अनुमोदित बधाई लाभार्थी"
    ),
    "NOTICE": (
        "public notice circular office order notification "
        "government announcement advisory press release "
        "attention general public information "
        "सार्वजनिक सूचना परिपत्र कार्यालय आदेश"
    ),
}

_scheme_embeddings = None
_doc_type_embeddings = None


def _get_scheme_embeddings():
    global _scheme_embeddings
    if _scheme_embeddings is None:
        model = get_model()
        texts = list(SCHEME_DESCRIPTIONS.values())
        _scheme_embeddings = model.encode(texts, convert_to_tensor=True)
    return _scheme_embeddings


def _get_doc_type_embeddings():
    global _doc_type_embeddings
    if _doc_type_embeddings is None:
        model = get_model()
        texts = list(DOCUMENT_TYPE_DESCRIPTIONS.values())
        _doc_type_embeddings = model.encode(texts, convert_to_tensor=True)
    return _doc_type_embeddings


def classify_with_indic_bert(ocr_text: str) -> Dict[str, Any]:
    """
    Classify document type and scheme using multilingual
    sentence embeddings with cosine similarity.
    """
    if not ocr_text or len(ocr_text.strip()) < 10:
        return {
            "document_type": "APPLICATION_FORM",
            "scheme_id": "unknown",
            "confidence": 0.0,
            "doc_type_confidence": 0.0,
            "method": "multilingual-bert",
        }

    try:
        model = get_model()

        # Use first 500 chars
        text = ocr_text[:500]

        # Encode query
        query_embedding = model.encode(text, convert_to_tensor=True)

        # --- Scheme classification ---
        scheme_embeddings = _get_scheme_embeddings()
        scheme_scores = util.cos_sim(query_embedding, scheme_embeddings)[0]
        scheme_scores_list = scheme_scores.tolist()

        # Softmax for confidence
        scheme_tensor = torch.tensor(scheme_scores_list)
        scheme_softmax = torch.softmax(scheme_tensor * 10, dim=0)
        best_scheme_idx = scheme_softmax.argmax().item()
        best_scheme = list(SCHEME_DESCRIPTIONS.keys())[best_scheme_idx]
        scheme_confidence = round(scheme_softmax[best_scheme_idx].item(), 3)

        # --- Document type classification ---
        doc_type_embeddings = _get_doc_type_embeddings()
        doc_type_scores = util.cos_sim(query_embedding, doc_type_embeddings)[0]
        doc_type_scores_list = doc_type_scores.tolist()

        doc_type_tensor = torch.tensor(doc_type_scores_list)
        doc_type_softmax = torch.softmax(doc_type_tensor * 10, dim=0)
        best_doc_type_idx = doc_type_softmax.argmax().item()
        best_doc_type = list(DOCUMENT_TYPE_DESCRIPTIONS.keys())[best_doc_type_idx]
        doc_type_confidence = round(doc_type_softmax[best_doc_type_idx].item(), 3)

        log.info(
            "indic_bert.classified",
            scheme=best_scheme,
            scheme_conf=scheme_confidence,
            doc_type=best_doc_type,
            doc_type_conf=doc_type_confidence,
        )

        return {
            "document_type": best_doc_type,
            "scheme_id": best_scheme,
            "confidence": scheme_confidence,
            "doc_type_confidence": doc_type_confidence,
            "method": "multilingual-bert",
        }

    except Exception as e:
        log.error("indic_bert.classification_failed", error=str(e))
        return {
            "document_type": "APPLICATION_FORM",
            "scheme_id": "unknown",
            "confidence": 0.0,
            "doc_type_confidence": 0.0,
            "method": "multilingual-bert-failed",
        }
