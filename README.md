<div align="center">

<img src="https://img.shields.io/badge/AI%20for%20Bharat-Hackathon%202025-FF6B00?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMiIgZmlsbD0iI0ZGOTkwMCIvPjwvc3ZnPg==" />
<img src="https://img.shields.io/badge/Bhashini-Powered-138808?style=for-the-badge" />
<img src="https://img.shields.io/badge/22-Indian%20Languages-000080?style=for-the-badge" />
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />

# 🇮🇳 CAIS — Citizen Application Intelligence System

### *Har naagrik ka haq, unki bhasha mein*
#### Every citizen's right, in their own language

**AI-powered document intelligence that eliminates middlemen and empowers citizens to navigate government schemes independently.**

[**🚀 Live Demo**](#) · [**📖 PRD**](./docs/PRD.md) · [**🔌 API Docs**](#api-reference) · [**🤝 Contributing**](#contributing)

</div>

---

## 🧭 The Problem

Every year, millions of eligible Indians are **rejected from welfare schemes** — not because they don't qualify, but because:

- 📄 Forms are filled incorrectly or incompletely
- 🔤 Rejection notices use bureaucratic language no one understands
- 🗣️ Government documents are in English/formal Hindi, inaccessible to regional language speakers
- 💸 Citizens end up paying **middlemen (dalals)** to navigate paperwork — exploiting the most vulnerable

**CAIS breaks this cycle.**

---

## ✨ What CAIS Does

Upload any government document → Get back a plain-language explanation, a readiness score, and an exact action plan — in **your language**.

| Feature | Description |
|---|---|
| 📊 **Document Readiness Score** | 0–100 score predicting approval likelihood before you submit |
| 🔍 **Rejection Analysis** | Every rejection reason extracted, translated, and turned into a fix-it checklist |
| 🌐 **22 Languages** | All scheduled Indian languages via Bhashini API |
| 📋 **Form Field Guidance** | Plain-language explanation of every field with examples and common mistake warnings |
| ⏰ **Deadline Detection** | All dates extracted, classified, and sorted nearest-first |
| 💾 **Progress Tracking** | Save and resume across sessions with visual completion indicator |
| ✅ **Document Validation** | Format, size, quality, and expiry checks before submission |
| 🧠 **Explainable AI** | Every score has a traceable reason — no black boxes |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                              │
│                   (React PWA — Mobile Responsive)                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │  Upload (JPEG / PNG / PDF ≤ 10MB)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT UPLOAD SERVICE                           │
│         FastAPI  ·  OpenCV (deskew/denoise/CLAHE)  ·  PyMuPDF       │
│              Format validation · Magic-number check                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │  Preprocessed image / PDF pages
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OCR ENGINE                                   │
│                                                                      │
│   ┌─────────────────────┐      ┌───────────────────────────────┐    │
│   │  OpenBharatOCR      │  OR  │  PaddleOCR / Parichay (CVIT)  │    │
│   │  (Primary)          │      │  (Fallback — confidence < 0.7) │    │
│   │  Aadhaar, PAN,      │      │  89.8% accuracy on Indian docs │    │
│   │  Passport, Voter ID │      │  JSON key-value output         │    │
│   └─────────────────────┘      └───────────────────────────────┘    │
│                                                                      │
│   Output: Text blocks + confidence scores + bounding boxes           │
│           Language detected per block (Devanagari, Tamil, etc.)      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
┌─────────────────────────┐   ┌────────────────────────────────────────┐
│   TRANSLATION SERVICE   │   │         DOCUMENT ANALYSIS ENGINE        │
│                         │   │                                         │
│  Bhashini API (ULCA)    │   │  1. Classify: Form / Notice / Other     │
│  bhashini_translator    │   │     └─ Keyword match + Indic-BERT       │
│                         │   │  2. Identify scheme                     │
│  • 22 scheduled langs   │   │     └─ Fuzzy match + form number regex  │
│  • Retry: 3x backoff    │   │  3. Extract fields, dates, IDs          │
│    (1s → 2s → 4s)       │   │     └─ spaCy NER + Indic NLP           │
│  • Redis cache (24h TTL)│   │  4. Parse rejection reasons             │
│  • Bureaucratic →       │   │     └─ Sarvam 2B LLM (semantic)        │
│    Plain language        │   │  5. Match against Scheme Knowledge Base │
└────────────┬────────────┘   └───────────────────┬─────────────────────┘
             │                                     │
             └──────────────┬──────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SCHEME KNOWLEDGE BASE                            │
│                                                                      │
│   PostgreSQL (structured rules)  ·  MongoDB (flexible field specs)   │
│                                                                      │
│   PM-KISAN  ·  Ayushman Bharat  ·  Ration Card                      │
│   Aadhaar Services  ·  Social Pension (Old Age / Widow / Disability) │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DECISION GENERATOR                             │
│                                                                      │
│   Readiness Score = (fields_complete × 0.60)                        │
│                   + (docs_present    × 0.30)                        │
│                   + (validation_pass × 0.10)                        │
│                                                                      │
│   🔴 Score < 70  → HIGH RISK OF REJECTION                           │
│   🟡 Score 70–89 → Medium Risk                                      │
│   🟢 Score ≥ 90  → Low Risk — Ready to Submit                       │
│                                                                      │
│   Output: Prioritized Action_Items · Deadlines · Missing Documents   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────────┐   ┌────────────────────────────────────────┐
│    PROGRESS TRACKER     │   │        STRUCTURED OUTPUT SERVICE        │
│                         │   │                                         │
│  Redis (active session) │   │  FastAPI + Pydantic models              │
│  PostgreSQL (persistent)│   │  Jinja2 multilingual templates          │
│  Action completion →    │   │  Export: PDF / JSON / Text              │
│  Score recalculation    │   │  Side-by-side: original + simplified    │
└─────────────────────────┘   └────────────────────────────────────────┘
```

---

## 🗂️ Repository Structure

```
cais/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── api/
│   │   ├── upload.py              # Document upload endpoints
│   │   ├── analysis.py            # Analysis & decision endpoints
│   │   ├── guidance.py            # Form field guidance endpoints
│   │   └── progress.py            # Progress tracking endpoints
│   ├── core/
│   │   ├── ocr/
│   │   │   ├── engine.py          # OCR orchestrator (primary + fallback)
│   │   │   ├── openbharat.py      # OpenBharatOCR wrapper
│   │   │   └── paddle_ocr.py      # PaddleOCR fallback wrapper
│   │   ├── translation/
│   │   │   ├── bhashini.py        # Bhashini API client + retry logic
│   │   │   └── cache.py           # Redis translation cache
│   │   ├── analysis/
│   │   │   ├── classifier.py      # Document type classifier (Indic-BERT)
│   │   │   ├── scheme_matcher.py  # Scheme identification
│   │   │   ├── field_extractor.py # NER-based field extraction
│   │   │   └── rejection.py       # Rejection reason parser (Sarvam 2B)
│   │   ├── scoring/
│   │   │   ├── readiness.py       # Readiness score calculator
│   │   │   └── decision.py        # Action item & deadline generator
│   │   └── preprocessing/
│   │       └── image.py           # OpenCV deskew/denoise/CLAHE
│   ├── db/
│   │   ├── postgres.py            # PostgreSQL client (schemes, progress)
│   │   ├── mongo.py               # MongoDB client (OCR results, analysis)
│   │   └── redis.py               # Redis client (sessions, cache)
│   ├── models/
│   │   ├── document.py            # Document Pydantic models
│   │   ├── scheme.py              # Scheme data models
│   │   ├── decision.py            # Decision output models
│   │   └── progress.py            # Progress state models
│   └── schemes/                   # Scheme Knowledge Base configs (JSON)
│       ├── pm_kisan.json
│       ├── ayushman_bharat.json
│       ├── ration_card.json
│       ├── aadhaar_services.json
│       └── social_pension.json
├── tests/
│   ├── unit/                      # pytest unit tests (80% coverage target)
│   ├── property/                  # Hypothesis property-based tests (34 properties)
│   └── integration/               # End-to-end pipeline tests
├── frontend/                      # React PWA
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Bhashini API key → [Register at bhashini.gov.in](https://bhashini.gov.in)

### 1. Clone & Setup

```bash
git clone https://github.com/your-team/cais.git
cd cais
cp .env.example .env
# Add your BHASHINI_API_KEY and database credentials to .env
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Infrastructure

```bash
docker-compose up -d
# Starts PostgreSQL, MongoDB, Redis
```

### 4. Initialize Scheme Knowledge Base

```bash
python scripts/seed_schemes.py
# Loads all 5 initial schemes into PostgreSQL
```

### 5. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

API live at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

---

## 🔌 API Reference

### Upload a Document

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@my_form.pdf" \
  -F "userId=user123" \
  -F "language=hi"   # ISO 639-1 code for Hindi
```

**Response:**
```json
{
  "documentId": "a1b2c3d4-...",
  "status": "queued"
}
```

### Get Analysis Result

```bash
curl http://localhost:8000/analysis/a1b2c3d4-...
```

**Response:**
```json
{
  "readinessScore": 62,
  "riskLevel": "HIGH",
  "schemeId": "pm-kisan",
  "schemeName": "PM Kisan Samman Nidhi",
  "actionItems": [
    {
      "actionId": "act_001",
      "title": "भूमि रिकॉर्ड अपलोड करें",
      "description": "आपका भूमि स्वामित्व दस्तावेज़ गायब है",
      "priority": 1,
      "category": "UPLOAD_DOCUMENT",
      "estimatedTime": "2-3 days",
      "steps": ["तहसीलदार कार्यालय जाएं", "खसरा/खतौनी की प्रति लें", ...],
      "isCompleted": false
    }
  ],
  "deadlines": [
    {
      "date": "2025-03-31",
      "description": "Application window closes",
      "daysRemaining": 45,
      "urgency": "UPCOMING"
    }
  ],
  "missingDocuments": [...]
}
```

### Get Form Field Help

```bash
curl http://localhost:8000/guidance/pm-kisan/khasra_number?language=ta
# Returns field guidance in Tamil
```

### Mark Action Complete

```bash
curl -X POST http://localhost:8000/progress/user123/a1b2c3d4-.../complete/act_001
```

**Response:** Updated decision with recalculated readiness score.

---

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/ -v --cov=app --cov-report=term-missing

# Property-based tests (34 correctness properties, 100 iterations each)
pytest tests/property/ -v

# All tests
pytest --cov=app --cov-fail-under=80
```

Property tests are tagged: `Feature: citizen-application-intelligence, Property {N}: {description}`

See [`docs/PROPERTIES.md`](./docs/PROPERTIES.md) for all 34 correctness properties.

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **API** | FastAPI + Uvicorn | Async, auto OpenAPI docs |
| **Image Processing** | OpenCV + Pillow + PyMuPDF | Deskew, denoise, CLAHE, PDF extraction |
| **OCR (Primary)** | [OpenBharatOCR](https://github.com/essentiasoftserv/openbharatocr) | Purpose-built for Indian gov IDs |
| **OCR (Fallback)** | PaddleOCR / Parichay (CVIT IIIT) | Complex layouts, 89.8% accuracy |
| **Translation** | [Bhashini API](https://bhashini.gov.in) + bhashini_translator | All 22 scheduled languages |
| **NLP/NER** | spaCy + Indic NLP Library | Field extraction: names, dates, IDs |
| **Classification** | Indic-BERT (ai4bharat, HuggingFace) | Document type classification |
| **LLM** | Sarvam 2B (sarvam-ai, HuggingFace) | Semantic rejection reason analysis |
| **Primary DB** | PostgreSQL | Scheme definitions, validation rules |
| **Document Store** | MongoDB | OCR results, analysis outputs |
| **Cache / Session** | Redis | Translation cache (24h TTL), active sessions |
| **Testing** | pytest + Hypothesis | Unit tests + 34 property-based tests |
| **Containers** | Docker + Docker Compose | Reproducible deployment |

---

## 📦 Open Source Credits

| Resource | Repo | Used For |
|---|---|---|
| OpenBharatOCR | `essentiasoftserv/openbharatocr` | OCR for Aadhaar, PAN, Passport, Voter ID |
| Bhashini API Examples | `bhashini-ai/bhashini-api-examples` | API integration reference |
| Lekhaanuvaad | `bhashini-dibd/lekhaanuvaad` | Pipeline architecture patterns |
| bhashini_translator | `dteklavya/bhashini_translator` | Python SDK for Bhashini |
| ULCA | `bhashini-dibd/ulca` | Language dataset formats |
| Parichay (CVIT IIIT) | IIIT Hyderabad research | Structured Indian doc extraction |
| Sarvam 2B | `sarvam-ai/sarvam-2b-v0.5` | Indic LLM for semantic analysis |
| Indic-BERT | `ai4bharat/indic-bert` | Document classification |
| Anuvaad ETL | `project-anuvaad/anuvaad` | Workflow orchestration patterns |

---

## 🌍 Supported Languages (22 Scheduled Languages)

`as` Assamese · `bn` Bengali · `brx` Bodo · `doi` Dogri · `gu` Gujarati · `hi` Hindi · `kn` Kannada · `ks` Kashmiri · `kok` Konkani · `mai` Maithili · `ml` Malayalam · `mni` Manipuri · `mr` Marathi · `ne` Nepali · `or` Odia · `pa` Punjabi · `sa` Sanskrit · `sat` Santali · `sd` Sindhi · `ta` Tamil · `te` Telugu · `ur` Urdu

---

## 📊 Correctness Properties

The system is governed by **34 formal correctness properties** that serve as the foundation for property-based testing. Key examples:

- **P5** — Bhashini API failure triggers exactly 3 retries (1s → 2s → 4s backoff)
- **P10** — All required fields present + all documents uploaded ⟹ readiness score = 100
- **P16** — Days remaining = deadline date − current date (exact calculation)
- **P21** — Score < 70 ⟹ risk level labeled "High Risk of Rejection"
- **P22** — Completing an Action_Item never decreases the readiness score

[→ Full property list in docs/PROPERTIES.md](./docs/PROPERTIES.md)

---

## 🗺️ Roadmap

**v1.0 (Hackathon)** — 5 schemes · 22 languages · Core pipeline
**v1.1** — Voice input via Bhashini ASR · Offline PWA mode · SMS deadline alerts
**v2.0** — DigiLocker integration · Direct portal submission · Predictive success scoring · 20+ schemes

---

## 🤝 Contributing

**Adding a new scheme is the easiest contribution — no code required.**

1. Copy `app/schemes/pm_kisan.json` as a template
2. Fill in scheme fields, required documents, validation rules
3. Submit a PR

For code contributions, please read [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 📄 License

MIT License — see [LICENSE](./LICENSE)

---

<div align="center">

Built with ❤️ for Bharat · AI for Bharat Hackathon 2025

*"The best welfare scheme is the one that actually reaches the citizen."*

</div>