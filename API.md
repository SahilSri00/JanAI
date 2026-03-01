# 🔌 CAIS — API Reference

> **Citizen Application Intelligence System**  
> Complete REST API documentation — all endpoints, request/response schemas, error codes, and integration examples.

---

## Base URL

```
Development:   http://localhost:8000/api/v1
Production:    https://api.cais.gov.in/v1
```

---

## Authentication

All endpoints require a user session token passed as a header.

```http
Authorization: Bearer <session_token>
Accept-Language: hi          # ISO 639-1 language code — controls response language
Content-Type: application/json
```

**Getting a session token:**
```http
POST /auth/session
{
  "userId": "string",         # Device ID or anonymous ID
  "languageCode": "hi"        # User's preferred language
}
```
```json
{
  "sessionToken": "eyJ...",
  "expiresIn": 86400,
  "userId": "usr_abc123"
}
```

---

## Global Response Envelope

Every response follows this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "requestId": "req_xyz789",
    "timestamp": "2025-03-15T10:30:00Z",
    "language": "hi",
    "processingMs": 342
  }
}
```

**Error envelope:**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "OCR_CONFIDENCE_TOO_LOW",
    "message": "तस्वीर की गुणवत्ता पर्याप्त नहीं है",
    "messageEn": "Image quality is not sufficient for text extraction",
    "suggestions": ["Take photo in better lighting", "Ensure all corners are visible"],
    "retryable": true
  },
  "meta": { ... }
}
```

---

## Endpoints

---

### 1. Health & Status

#### `GET /health`

Check API availability.

**Response `200`:**
```json
{
  "status": "healthy",
  "services": {
    "ocr": "up",
    "bhashini": "up",
    "postgres": "up",
    "mongodb": "up",
    "redis": "up"
  },
  "version": "1.0.0"
}
```

**Response `503`** (partial degradation):
```json
{
  "status": "degraded",
  "services": {
    "ocr": "up",
    "bhashini": "down",
    "estimatedRestoration": "2025-03-15T11:00:00Z"
  }
}
```

---

### 2. Session & Language

#### `POST /session`

Create or update a user session with language preference.

**Request:**
```json
{
  "userId": "usr_abc123",          # Required — device ID or anonymous UUID
  "languageCode": "ta",            # Required — ISO 639-1 from 22 scheduled languages
  "deviceInfo": {                  # Optional — for analytics
    "platform": "android",
    "appVersion": "1.0.0"
  }
}
```

**Response `200`:**
```json
{
  "sessionToken": "eyJhbGci...",
  "userId": "usr_abc123",
  "languageCode": "ta",
  "languageName": "Tamil",
  "expiresIn": 86400
}
```

**Supported language codes:**

| Code | Language | Script |
|------|----------|--------|
| `as` | Assamese | Bengali |
| `bn` | Bengali | Bengali |
| `brx` | Bodo | Devanagari |
| `doi` | Dogri | Devanagari |
| `gu` | Gujarati | Gujarati |
| `hi` | Hindi | Devanagari |
| `kn` | Kannada | Kannada |
| `ks` | Kashmiri | Perso-Arabic |
| `kok` | Konkani | Devanagari |
| `mai` | Maithili | Devanagari |
| `ml` | Malayalam | Malayalam |
| `mni` | Manipuri | Meitei |
| `mr` | Marathi | Devanagari |
| `ne` | Nepali | Devanagari |
| `or` | Odia | Odia |
| `pa` | Punjabi | Gurmukhi |
| `sa` | Sanskrit | Devanagari |
| `sat` | Santali | Ol Chiki |
| `sd` | Sindhi | Perso-Arabic |
| `ta` | Tamil | Tamil |
| `te` | Telugu | Telugu |
| `ur` | Urdu | Perso-Arabic |

---

### 3. Document Upload

#### `POST /documents/upload`

Upload a government document for analysis.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | `File` | ✅ | JPEG, PNG, or PDF. Max 10MB |
| `documentType` | `string` | ❌ | Hint: `APPLICATION_FORM` \| `REJECTION_NOTICE` \| `SUPPORTING_DOC` |
| `schemeId` | `string` | ❌ | Hint if known: `pm-kisan`, `ayushman-bharat`, etc. |

```bash
curl -X POST https://api.cais.gov.in/v1/documents/upload \
  -H "Authorization: Bearer <token>" \
  -H "Accept-Language: hi" \
  -F "file=@ration_form.pdf" \
  -F "documentType=APPLICATION_FORM"
```

**Response `202` (Accepted — processing started):**
```json
{
  "documentId": "doc_8f3k2m",
  "status": "QUEUED",
  "estimatedProcessingSeconds": 12,
  "wsEndpoint": "wss://api.cais.gov.in/v1/documents/doc_8f3k2m/stream"
}
```

**Error `400`:**
```json
{
  "error": {
    "code": "INVALID_FILE_FORMAT",
    "message": "केवल JPEG, PNG, और PDF फ़ाइलें स्वीकृत हैं",
    "messageEn": "Only JPEG, PNG, and PDF files are accepted",
    "suggestions": ["Convert your file to PDF before uploading"],
    "retryable": true
  }
}
```

**Error `413`:**
```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "फ़ाइल का आकार 10MB से अधिक है (आपकी फ़ाइल: 14.2MB)",
    "suggestions": ["Compress your PDF", "Take photo at lower resolution"],
    "retryable": true
  }
}
```

---

#### `GET /documents/{documentId}/status`

Poll processing status (fallback when WebSocket unavailable).

**Response `200`:**
```json
{
  "documentId": "doc_8f3k2m",
  "status": "OCR_PROCESSING",          # QUEUED | OCR_PROCESSING | TRANSLATING | ANALYZING | COMPLETED | FAILED
  "progress": 40,                       # 0–100
  "currentStage": "Reading document text",
  "currentStageHi": "दस्तावेज़ का पाठ पढ़ा जा रहा है",
  "stages": [
    { "name": "received",      "status": "done",    "completedAt": "2025-03-15T10:30:01Z" },
    { "name": "preprocessing", "status": "done",    "completedAt": "2025-03-15T10:30:02Z" },
    { "name": "ocr",           "status": "active",  "startedAt":   "2025-03-15T10:30:02Z" },
    { "name": "translating",   "status": "pending", "completedAt": null },
    { "name": "analyzing",     "status": "pending", "completedAt": null },
    { "name": "decision",      "status": "pending", "completedAt": null }
  ]
}
```

---

#### `WebSocket /documents/{documentId}/stream`

Real-time processing updates. Connect immediately after upload.

**Server → Client messages:**

```json
// Stage update
{ "event": "stage_update", "stage": "ocr", "progress": 40, "message": "Reading text..." }

// OCR result preview
{ "event": "ocr_complete", "confidence": 0.87, "pageCount": 2, "languagesDetected": ["hi", "en"] }

// Translation complete
{ "event": "translation_complete", "schemeDetected": "PM-KISAN", "schemeConfidence": 0.94 }

// Final result
{ "event": "complete", "documentId": "doc_8f3k2m", "readinessScore": 62 }

// Error
{ "event": "error", "code": "OCR_FAILED", "message": "...", "retryable": true }
```

---

### 4. Analysis & Decision

#### `GET /documents/{documentId}/analysis`

Get complete analysis result after processing is complete.

**Response `200`:**
```json
{
  "documentId": "doc_8f3k2m",
  "documentType": "APPLICATION_FORM",
  "scheme": {
    "schemeId": "pm-kisan",
    "schemeName": "PM Kisan Samman Nidhi",
    "schemeNameHi": "प्रधानमंत्री किसान सम्मान निधि",
    "department": "Ministry of Agriculture",
    "confidence": 0.94
  },
  "readinessScore": 62,
  "riskLevel": "HIGH",                # LOW | MEDIUM | HIGH
  "riskMessage": "आपका आवेदन अस्वीकार होने की संभावना अधिक है",
  "riskMessageEn": "Your application has a high chance of rejection",
  "actionItems": [
    {
      "actionId": "act_001",
      "title": "भूमि रिकॉर्ड अपलोड करें",
      "titleEn": "Upload land records",
      "description": "आपके भूमि स्वामित्व का प्रमाण गायब है। खतौनी या खसरा की प्रति आवश्यक है।",
      "descriptionEn": "Proof of land ownership is missing. A copy of Khatauni or Khasra is required.",
      "priority": 1,
      "category": "UPLOAD_DOCUMENT",        # FILL_FIELD | UPLOAD_DOCUMENT | CORRECT_ERROR | VERIFY_INFO
      "severity": "CRITICAL",               # CRITICAL | RECOMMENDED
      "estimatedTime": "2-3 days",
      "estimatedMinutes": 2880,
      "steps": [
        {
          "stepNumber": 1,
          "instruction": "अपने तहसीलदार कार्यालय जाएं",
          "instructionEn": "Go to your Tehsildar office",
          "tip": "सोमवार-शनिवार, सुबह 10 बजे से शाम 5 बजे तक खुला रहता है"
        },
        {
          "stepNumber": 2,
          "instruction": "खतौनी / खसरा की प्रति मांगें",
          "instructionEn": "Ask for a copy of Khatauni / Khasra"
        },
        {
          "stepNumber": 3,
          "instruction": "अधिकारी से हस्ताक्षर और मुहर लगवाएं",
          "instructionEn": "Get it signed and stamped by the officer"
        },
        {
          "stepNumber": 4,
          "instruction": "सभी पृष्ठों की स्पष्ट फोटो लें और यहाँ अपलोड करें",
          "instructionEn": "Take a clear photo of all pages and upload here"
        }
      ],
      "relatedFields": ["khasra_number", "land_area"],
      "isCompleted": false,
      "completedAt": null
    },
    {
      "actionId": "act_002",
      "title": "बैंक खाते को आधार से जोड़ें",
      "titleEn": "Link bank account to Aadhaar",
      "priority": 2,
      "category": "VERIFY_INFO",
      "severity": "CRITICAL",
      "estimatedTime": "15 minutes",
      "estimatedMinutes": 15,
      "steps": [ ... ],
      "isCompleted": false
    },
    {
      "actionId": "act_003",
      "title": "मोबाइल नंबर अपडेट करें",
      "priority": 3,
      "severity": "RECOMMENDED",
      "estimatedTime": "10 minutes",
      "isCompleted": false
    }
  ],
  "deadlines": [
    {
      "deadlineId": "ddl_001",
      "description": "Application window closes",
      "descriptionHi": "आवेदन विंडो बंद होती है",
      "date": "2025-03-31",
      "daysRemaining": 16,
      "urgency": "SOON",              # IMMEDIATE (<3 days) | SOON (<14 days) | UPCOMING (14+ days)
      "associatedActions": ["act_001", "act_002"]
    }
  ],
  "missingDocuments": [
    {
      "documentType": "land_records",
      "description": "Khatauni or Khasra copy",
      "descriptionHi": "खतौनी या खसरा प्रति",
      "isMandatory": true,
      "howToObtain": "Tehsildar office or Bhulekh online portal",
      "howToObtainHi": "तहसीलदार कार्यालय या भूलेख ऑनलाइन पोर्टल",
      "estimatedTime": "2-3 days",
      "onlineLink": "https://bhulekh.up.nic.in"
    }
  ],
  "extractedFields": [
    {
      "fieldName": "applicant_name",
      "fieldValue": "Ramesh Kumar",
      "isRequired": true,
      "isComplete": true,
      "confidence": 0.97
    },
    {
      "fieldName": "khasra_number",
      "fieldValue": null,
      "isRequired": true,
      "isComplete": false,
      "confidence": null
    }
  ],
  "ocrMetadata": {
    "overallConfidence": 0.87,
    "pageCount": 1,
    "languagesDetected": ["hi", "en"],
    "processingMs": 3240
  }
}
```

**Error `404`:**
```json
{ "error": { "code": "DOCUMENT_NOT_FOUND", "message": "दस्तावेज़ नहीं मिला" } }
```

**Error `409`** (still processing):
```json
{ "error": { "code": "PROCESSING_INCOMPLETE", "status": "TRANSLATING", "progress": 60 } }
```

---

#### `GET /documents/{documentId}/rejection-analysis`

Detailed rejection notice breakdown (only for `REJECTION_NOTICE` document type).

**Response `200`:**
```json
{
  "documentId": "doc_8f3k2m",
  "documentType": "REJECTION_NOTICE",
  "scheme": { ... },
  "rejectionReasons": [
    {
      "reasonId": "rej_001",
      "originalText": "आवेदक के दस्तावेज़ में भूमि रिकॉर्ड का सत्यापन नहीं हुआ",
      "simplifiedText": "आपके भूमि स्वामित्व का कागज़ सही नहीं था",
      "simplifiedTextEn": "Your land ownership document could not be verified",
      "category": "MISSING_DOCUMENT",
      "severity": "CRITICAL",
      "linkedActionItems": ["act_001"]
    },
    {
      "reasonId": "rej_002",
      "originalText": "बैंक खाता आधार से असंबद्ध",
      "simplifiedText": "आपका बैंक खाता आधार कार्ड से जुड़ा नहीं है",
      "simplifiedTextEn": "Bank account is not linked to Aadhaar card",
      "category": "VERIFICATION_FAILED",
      "severity": "CRITICAL",
      "linkedActionItems": ["act_002"]
    }
  ],
  "groupedActionItems": [
    {
      "groupName": "Document Issues",
      "groupNameHi": "दस्तावेज़ संबंधी समस्याएं",
      "actionItems": ["act_001"],
      "combinedReasons": ["rej_001"]
    },
    {
      "groupName": "Verification Issues",
      "groupNameHi": "सत्यापन संबंधी समस्याएं",
      "actionItems": ["act_002"],
      "combinedReasons": ["rej_002"]
    }
  ],
  "reapplicationGuidance": {
    "canReapply": true,
    "reapplyBy": "2025-06-30",
    "reapplyPortal": "https://pmkisan.gov.in",
    "estimatedFixTime": "3-5 days"
  }
}
```

---

### 5. Form Field Guidance

#### `GET /schemes/{schemeId}/fields/{fieldId}/guidance`

Get plain-language help for a specific form field.

**Path params:**
- `schemeId` — e.g., `pm-kisan`, `ayushman-bharat`, `ration-card`, `aadhaar-services`, `social-pension`
- `fieldId` — e.g., `khasra_number`, `aadhaar_number`, `bank_ifsc`

```bash
GET /schemes/pm-kisan/fields/khasra_number/guidance
Accept-Language: ta
```

**Response `200`:**
```json
{
  "fieldId": "khasra_number",
  "fieldName": "கசரா எண்",
  "fieldNameEn": "Khasra Number",
  "fieldType": "NUMBER",
  "isRequired": true,
  "helpText": "இது உங்கள் நில கணக்கு எண். அரசு நில வரைபடத்தில் உங்கள் நிலத்தின் தனி எண்.",
  "helpTextEn": "This is the unique number of your land plot as recorded in government land maps.",
  "formatRules": {
    "pattern": "^[0-9]{1,8}(/[0-9]{1,4})?$",
    "description": "1 to 8 digits, optionally followed by /fraction (e.g., 425 or 425/2)",
    "examples": ["425", "1203", "88/2", "5467/1"]
  },
  "commonMistakes": [
    {
      "mistake": "Confusing Khasra number with Khata number",
      "mistakeHi": "खसरा नंबर को खाता नंबर समझ लेना",
      "correction": "Khasra is the plot number. Khata is the owner account number. Both are different."
    },
    {
      "mistake": "Leaving blank for multiple plots",
      "correction": "If you have multiple plots, list all Khasra numbers separated by commas."
    }
  ],
  "acceptedDocuments": [
    {
      "documentName": "Khatauni",
      "documentNameHi": "खतौनी",
      "howToGet": "Tehsildar office",
      "onlineLink": "https://bhulekh.up.nic.in",
      "states": ["UP", "MP", "RJ"]
    },
    {
      "documentName": "Jamabandi",
      "documentNameHi": "जमाबंदी",
      "howToGet": "Patwari office",
      "states": ["HR", "PB", "HP"]
    },
    {
      "documentName": "Pahani / RTC",
      "howToGet": "Revenue department",
      "onlineLink": "https://mee-bhoomi.telangana.gov.in",
      "states": ["TS", "AP", "KA"]
    }
  ]
}
```

---

#### `GET /schemes/{schemeId}/fields`

Get all fields for a scheme (used to build form guidance overview).

**Response `200`:**
```json
{
  "schemeId": "pm-kisan",
  "totalFields": 12,
  "requiredFields": 8,
  "fields": [
    {
      "fieldId": "applicant_name",
      "fieldName": "आवेदक का नाम",
      "isRequired": true,
      "fieldType": "TEXT",
      "hasGuidance": true
    },
    ...
  ]
}
```

---

### 6. Document Validation

#### `POST /documents/validate`

Validate a supporting document before attaching to an application.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | `File` | ✅ | Document to validate |
| `documentType` | `string` | ✅ | e.g., `aadhaar`, `pan`, `land_records`, `income_certificate` |
| `schemeId` | `string` | ❌ | If provided, checks scheme-specific requirements |

**Response `200`:**
```json
{
  "documentType": "aadhaar",
  "overallResult": "PASS",         # PASS | FAIL | WARNING
  "checks": [
    {
      "checkName": "file_format",
      "checkNameHi": "फ़ाइल प्रारूप",
      "status": "PASS",
      "detail": "JPEG format accepted"
    },
    {
      "checkName": "file_size",
      "status": "PASS",
      "detail": "2.1 MB — within 10MB limit"
    },
    {
      "checkName": "image_quality",
      "status": "PASS",
      "detail": "Clarity score: 87/100 — readable"
    },
    {
      "checkName": "corners_visible",
      "status": "PASS",
      "detail": "All 4 corners detected"
    },
    {
      "checkName": "expiry_date",
      "status": "PASS",
      "detail": "Aadhaar does not expire"
    },
    {
      "checkName": "text_readable",
      "status": "PASS",
      "detail": "Name and UID number extracted successfully"
    }
  ],
  "extractedInfo": {
    "documentSubtype": "aadhaar_card",
    "nameDetected": true,
    "idNumberDetected": true,
    "expiryDate": null,
    "isExpired": false
  },
  "recommendation": "This document is ready to submit."
}
```

**Response `200` with failures:**
```json
{
  "overallResult": "FAIL",
  "checks": [
    { "checkName": "image_quality", "status": "FAIL",
      "detail": "Clarity score: 18/100 — too blurry",
      "fix": "Hold phone steady with both hands. Tap screen to focus before capturing." },
    { "checkName": "expiry_date",   "status": "FAIL",
      "detail": "Document expired: January 2023",
      "fix": "This ID is expired. Please obtain a renewed/valid identity document." }
  ]
}
```

---

### 7. Progress Tracking

#### `GET /users/{userId}/progress`

Get all application progress states for a user.

**Response `200`:**
```json
{
  "userId": "usr_abc123",
  "applications": [
    {
      "documentId": "doc_8f3k2m",
      "schemeId": "pm-kisan",
      "schemeName": "PM Kisan Samman Nidhi",
      "currentScore": 74,
      "riskLevel": "MEDIUM",
      "totalActions": 3,
      "completedActions": 1,
      "completionPercentage": 33,
      "lastUpdated": "2025-03-14T18:22:00Z",
      "isReadyToSubmit": false
    },
    {
      "documentId": "doc_9k1p3n",
      "schemeId": "ration-card",
      "currentScore": 100,
      "riskLevel": "LOW",
      "totalActions": 4,
      "completedActions": 4,
      "completionPercentage": 100,
      "lastUpdated": "2025-03-13T12:00:00Z",
      "isReadyToSubmit": true
    }
  ]
}
```

---

#### `GET /users/{userId}/progress/{documentId}`

Get detailed progress state for one application.

**Response `200`:**
```json
{
  "userId": "usr_abc123",
  "documentId": "doc_8f3k2m",
  "currentScore": 74,
  "riskLevel": "MEDIUM",
  "completionPercentage": 33,
  "completedActions": ["act_003"],
  "pendingActions": ["act_001", "act_002"],
  "uploadedDocuments": [],
  "lastUpdated": "2025-03-14T18:22:00Z",
  "isReadyToSubmit": false
}
```

---

#### `POST /users/{userId}/progress/{documentId}/actions/{actionId}/complete`

Mark an action item as complete and trigger score recalculation.

**Request body:** *(optional)*
```json
{
  "completionNote": "Uploaded Khatauni from Bhulekh portal",
  "attachmentDocumentId": "doc_validate_001"   # If a document was uploaded to prove completion
}
```

**Response `200`:**
```json
{
  "actionId": "act_001",
  "isCompleted": true,
  "completedAt": "2025-03-15T10:45:00Z",
  "previousScore": 62,
  "newScore": 82,
  "scoreDelta": 20,
  "newRiskLevel": "MEDIUM",
  "remainingCriticalActions": 1,
  "isReadyToSubmit": false,
  "nextAction": {
    "actionId": "act_002",
    "title": "बैंक खाते को आधार से जोड़ें",
    "estimatedTime": "15 minutes"
  }
}
```

**Special response when all actions complete:**
```json
{
  "newScore": 100,
  "scoreDelta": 18,
  "newRiskLevel": "LOW",
  "isReadyToSubmit": true,
  "celebration": true,
  "submissionGuidance": {
    "portalUrl": "https://pmkisan.gov.in",
    "cscLocatorUrl": "https://locator.csccloud.in",
    "message": "आपका आवेदन पूर्ण है। अब इसे जमा करें।"
  }
}
```

---

#### `POST /users/{userId}/progress/{documentId}/actions/{actionId}/undo`

Undo a completed action (user realizes they made a mistake).

**Response `200`:**
```json
{
  "actionId": "act_001",
  "isCompleted": false,
  "previousScore": 82,
  "newScore": 62,
  "scoreDelta": -20
}
```

---

### 8. Export

#### `GET /documents/{documentId}/export`

Export analysis results as a downloadable file.

**Query params:**
- `format` — `pdf` | `json` | `text`

```bash
GET /documents/doc_8f3k2m/export?format=pdf
Accept-Language: hi
```

**Response `200`:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="cais_report_pm-kisan_20250315.pdf"
<binary PDF data>
```

The PDF includes: scheme name, readiness score, all action items with steps, deadlines, and missing documents — all in the user's preferred language.

---

### 9. Schemes

#### `GET /schemes`

List all supported schemes.

**Response `200`:**
```json
{
  "schemes": [
    {
      "schemeId": "pm-kisan",
      "schemeName": "PM Kisan Samman Nidhi",
      "schemeNameHi": "प्रधानमंत्री किसान सम्मान निधि",
      "department": "Ministry of Agriculture",
      "description": "Direct income support of ₹6000/year for small farmers",
      "targetBeneficiary": "Small and marginal farmers",
      "processingDays": { "average": 30, "max": 60 },
      "portalUrl": "https://pmkisan.gov.in",
      "isActive": true
    },
    ...
  ]
}
```

---

#### `GET /schemes/{schemeId}`

Get complete scheme definition.

**Response `200`:**
```json
{
  "schemeId": "pm-kisan",
  "schemeName": "PM Kisan Samman Nidhi",
  "department": "Ministry of Agriculture",
  "eligibilityCriteria": [
    "Must own cultivable land",
    "Annual family income below ₹2 lakh",
    "Must have Aadhaar card"
  ],
  "requiredDocuments": [
    {
      "documentType": "land_records",
      "isMandatory": true,
      "acceptedFormats": ["Khatauni", "Khasra", "Jamabandi", "Pahani"],
      "notes": "Must be updated within last 2 years"
    },
    {
      "documentType": "aadhaar",
      "isMandatory": true,
      "acceptedFormats": ["Aadhaar card copy", "e-Aadhaar PDF"]
    },
    {
      "documentType": "bank_passbook",
      "isMandatory": true,
      "notes": "Account must be linked to Aadhaar"
    }
  ],
  "formFields": [ ... ],
  "processingTimeline": { "averageDays": 30, "maxDays": 60 }
}
```

---

## Error Code Reference

| Code | HTTP | Meaning | Retryable |
|------|------|---------|-----------|
| `INVALID_FILE_FORMAT` | 400 | File is not JPEG, PNG, or PDF | ✅ (with correct file) |
| `FILE_TOO_LARGE` | 413 | File exceeds 10MB | ✅ (compress first) |
| `FILE_CORRUPTED` | 400 | File cannot be read/opened | ✅ (re-export/retake) |
| `OCR_CONFIDENCE_TOO_LOW` | 422 | Image quality too poor | ✅ (better photo) |
| `OCR_PROCESSING_FAILED` | 500 | OCR engine internal error | ✅ (auto-retry) |
| `BHASHINI_UNAVAILABLE` | 503 | Translation service down | ✅ (3 auto-retries) |
| `BHASHINI_LANG_UNSUPPORTED` | 400 | Language pair not supported | ❌ |
| `SCHEME_NOT_FOUND` | 404 | Scheme ID doesn't exist | ❌ |
| `SCHEME_NOT_SUPPORTED` | 422 | Document's scheme not in initial 5 | ❌ |
| `DOCUMENT_NOT_FOUND` | 404 | documentId doesn't exist | ❌ |
| `PROCESSING_INCOMPLETE` | 409 | Analysis still in progress | ✅ (poll /status) |
| `ACTION_NOT_FOUND` | 404 | actionId doesn't exist | ❌ |
| `UNAUTHORIZED` | 401 | Invalid or expired session token | ✅ (re-auth) |
| `RATE_LIMITED` | 429 | Too many requests | ✅ (wait + retry) |
| `INTERNAL_ERROR` | 500 | Unexpected server error | ✅ |

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /documents/upload` | 10 requests | 1 hour per user |
| `POST /documents/validate` | 20 requests | 1 hour per user |
| `GET /documents/*/analysis` | 60 requests | 1 minute per user |
| `GET /schemes/*/fields/*/guidance` | 120 requests | 1 minute per user |
| All other endpoints | 200 requests | 1 minute per user |

Rate limit headers returned on every response:
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1710498600
```

---

## Webhooks *(Phase 2)*

Register a webhook to receive processing completion callbacks:

```http
POST /webhooks
{
  "url": "https://your-server.com/cais-callback",
  "events": ["document.completed", "document.failed"]
}
```

Payload on `document.completed`:
```json
{
  "event": "document.completed",
  "documentId": "doc_8f3k2m",
  "readinessScore": 62,
  "riskLevel": "HIGH",
  "timestamp": "2025-03-15T10:30:45Z"
}
```

---

## SDK Quickstart (Python)

```python
from cais_sdk import CAISClient

client = CAISClient(
    base_url="https://api.cais.gov.in/v1",
    language="hi"
)

# Authenticate
session = client.create_session(user_id="usr_abc123")

# Upload document
with open("pm_kisan_form.pdf", "rb") as f:
    doc = client.upload_document(f, document_type="APPLICATION_FORM")

# Wait for processing (handles WebSocket + polling fallback)
result = client.wait_for_analysis(doc.document_id, timeout=30)

# Get results
print(f"Score: {result.readiness_score}")
print(f"Risk: {result.risk_level}")
for action in result.action_items:
    print(f"  [{action.severity}] {action.title} — {action.estimated_time}")
```

---

*All responses include translated content in the user's preferred language as set in session or `Accept-Language` header.*