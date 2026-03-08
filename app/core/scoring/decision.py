from typing import List, Dict


# Estimated time to complete each action
ESTIMATED_TIME: Dict[str, str] = {
    # Field actions
    "field_applicant_name":   "5 minutes",
    "field_father_name":      "5 minutes",
    "field_date_of_birth":    "5 minutes",
    "field_aadhaar_number":   "5 minutes",
    "field_mobile_number":    "5 minutes",
    "field_bank_account":     "10 minutes",
    "field_ifsc_code":        "10 minutes",
    "field_khasra_number":    "15 minutes",
    "field_land_area":        "15 minutes",
    "field_family_members":   "5 minutes",
    "field_income_level":     "10 minutes",
    "field_pension_type":     "5 minutes",
    "field_correction_field": "10 minutes",
    "field_address":          "10 minutes",
    # Document actions
    "doc_aadhaar_card":        "1 day",
    "doc_land_records":        "3-5 days",
    "doc_bank_passbook":       "1 day",
    "doc_ration_card":         "3-5 days",
    "doc_income_certificate":  "3-7 days",
    "doc_address_proof":       "1-2 days",
    "doc_identity_proof":      "1-2 days",
    "doc_passport_photo":      "1 day",
    "doc_age_proof":           "2-3 days",
}


FIELD_HINTS: Dict[str, Dict[str, str]] = {
    "applicant_name": {
        "title_hi": "आवेदक का नाम भरें",
        "title_en": "Fill applicant name",
        "hint_hi": "फॉर्म में जहाँ 'Applicant Name' या 'आवेदक का नाम' लिखा है, अपना पूरा नाम जैसा दस्तावेज़ों में है वैसा भरें।",
        "hint_en": "Enter your full name exactly as it appears on your official documents.",
    },
    "father_name": {
        "title_hi": "पिता का नाम भरें",
        "title_en": "Fill father's name",
        "hint_hi": "फॉर्म में पिता/पति का नाम पूछा हो तो पूरा नाम साफ-साफ लिखें।",
        "hint_en": "Write your father's (or husband's) full name clearly where asked.",
    },
    "aadhaar_number": {
        "title_hi": "आधार नंबर दर्ज करें",
        "title_en": "Enter Aadhaar number",
        "hint_hi": "12 अंकों का आधार नंबर बिना गलती के भरें।",
        "hint_en": "Enter your 12-digit Aadhaar number carefully, matching your Aadhaar card.",
    },
    "mobile_number": {
        "title_hi": "मोबाइल नंबर भरें",
        "title_en": "Fill mobile number",
        "hint_hi": "ऐसा मोबाइल नंबर लिखें जो आपके नाम पर हो और OTP रिसीव कर सके।",
        "hint_en": "Use a mobile number that is active and can receive OTP messages.",
    },
    "bank_account": {
        "title_hi": "बैंक खाता विवरण भरें",
        "title_en": "Fill bank account details",
        "hint_hi": "सही खाता संख्या लिखें, पासबुक या बैंक स्टेटमेंट से कॉपी करें।",
        "hint_en": "Copy the account number from your bank passbook or statement.",
    },
    "ifsc_code": {
        "title_hi": "IFSC कोड भरें",
        "title_en": "Fill IFSC code",
        "hint_hi": "ब्रांच का IFSC कोड पासबुक या बैंक वेबसाइट से देखें।",
        "hint_en": "Use the IFSC printed on your passbook or bank's official website.",
    },
    "khasra_number": {
        "title_hi": "खसरा नंबर भरें",
        "title_en": "Fill Khasra number",
        "hint_hi": "राजस्व रिकॉर्ड/खसरा-खतौनी से नंबर कॉपी करें।",
        "hint_en": "Copy the Khasra number from official land records, not from memory.",
    },
    "land_area": {
        "title_hi": "भूमि का क्षेत्रफल भरें",
        "title_en": "Fill land area",
        "hint_hi": "कितनी भूमि आपके नाम है (हेक्टेयर/एकड़) सही-सही भरें।",
        "hint_en": "Enter the land area in hectares/acres as per your land record.",
    },
    "family_members": {
        "title_hi": "परिवार के सदस्यों की संख्या भरें",
        "title_en": "Fill number of family members",
        "hint_hi": "परिवार में कुल कितने सदस्य हैं, वो संख्या सही-सही भरें।",
        "hint_en": "Enter the total number of members in your household.",
    },
    "income_level": {
        "title_hi": "वार्षिक आय भरें",
        "title_en": "Fill annual income",
        "hint_hi": "परिवार की कुल वार्षिक आय रुपयों में भरें।",
        "hint_en": "Enter your total annual household income in rupees.",
    },
    "pension_type": {
        "title_hi": "पेंशन का प्रकार चुनें",
        "title_en": "Select pension type",
        "hint_hi": "वृद्धावस्था, विधवा, या विकलांगता में से सही पेंशन प्रकार चुनें।",
        "hint_en": "Select the correct pension type: old age, widow, or disability.",
    },
    "correction_field": {
        "title_hi": "सुधार का विवरण भरें",
        "title_en": "Fill correction details",
        "hint_hi": "आधार में जो सुधार चाहिए उसका विवरण सही-सही भरें।",
        "hint_en": "Specify which field needs correction in your Aadhaar.",
    },
    "date_of_birth": {
        "title_hi": "जन्म तिथि भरें",
        "title_en": "Fill date of birth",
        "hint_hi": "जन्म तिथि DD/MM/YYYY फॉर्मेट में आधार कार्ड के अनुसार भरें।",
        "hint_en": "Enter your date of birth in DD/MM/YYYY format as per Aadhaar.",
    },
    "address": {
        "title_hi": "पता भरें",
        "title_en": "Fill address",
        "hint_hi": "पूरा पता जैसा आधार या पते के प्रमाण पर है वैसा भरें।",
        "hint_en": "Enter your full address exactly as on your address proof document.",
    },
}


DOCUMENT_HINTS: Dict[str, Dict[str, str]] = {
    "aadhaar_card": {
        "title_hi": "आधार कार्ड की कॉपी जोड़ें",
        "title_en": "Attach Aadhaar card copy",
        "hint_hi": "आधार कार्ड की साफ फोटो या स्कैन PDF अपलोड करें।",
        "hint_en": "Upload a clear photo or PDF scan of your Aadhaar card with the number visible.",
    },
    "land_records": {
        "title_hi": "भूमि रिकॉर्ड (खसरा/खतौनी) जोड़ें",
        "title_en": "Attach land record",
        "hint_hi": "तहसील या ऑनलाइन पोर्टल से खसरा/खतौनी की प्रति लें और अपलोड करें।",
        "hint_en": "Obtain a copy of your land record from tehsil/online portal and upload it.",
    },
    "bank_passbook": {
        "title_hi": "बैंक पासबुक की कॉपी जोड़ें",
        "title_en": "Attach bank passbook copy",
        "hint_hi": "पासबुक के पहले पेज की साफ फोटो लें जिसमें नाम, खाता संख्या और IFSC दिखे।",
        "hint_en": "Upload a clear photo of the first page showing name, account number, and IFSC.",
    },
    "income_certificate": {
        "title_hi": "आय प्रमाण पत्र जोड़ें",
        "title_en": "Attach income certificate",
        "hint_hi": "तहसील/CSC से नवीनतम आय प्रमाण पत्र बनवाकर उसकी कॉपी अपलोड करें।",
        "hint_en": "Get a recent income certificate from tehsil/CSC and upload its scan.",
    },
    "ration_card": {
        "title_hi": "राशन कार्ड की कॉपी जोड़ें",
        "title_en": "Attach ration card copy",
        "hint_hi": "परिवार के राशन कार्ड की कॉपी अपलोड करें।",
        "hint_en": "Upload a copy of your family ration card showing all household members.",
    },
    "address_proof": {
        "title_hi": "पते का प्रमाण जोड़ें",
        "title_en": "Attach address proof",
        "hint_hi": "बिजली बिल, राशन कार्ड, या आधार पते का प्रमाण अपलोड करें।",
        "hint_en": "Upload electricity bill, ration card, or Aadhaar as address proof.",
    },
    "identity_proof": {
        "title_hi": "पहचान प्रमाण जोड़ें",
        "title_en": "Attach identity proof",
        "hint_hi": "आधार, पैन, या वोटर ID में से कोई एक पहचान प्रमाण अपलोड करें।",
        "hint_en": "Upload Aadhaar, PAN, or Voter ID as identity proof.",
    },
    "passport_photo": {
        "title_hi": "पासपोर्ट साइज़ फोटो जोड़ें",
        "title_en": "Attach passport size photo",
        "hint_hi": "हाल की पासपोर्ट साइज़ फोटो अपलोड करें।",
        "hint_en": "Upload a recent passport size photograph with white background.",
    },
    "age_proof": {
        "title_hi": "आयु प्रमाण जोड़ें",
        "title_en": "Attach age proof",
        "hint_hi": "जन्म प्रमाण पत्र या आधार आयु प्रमाण के रूप में अपलोड करें।",
        "hint_en": "Upload birth certificate or Aadhaar as age proof.",
    },
}


def _base_priority_for_field(field_id: str) -> int:
    critical = {"aadhaar_number", "bank_account", "ifsc_code"}
    contact = {"mobile_number"}
    if field_id in critical:
        return 1
    if field_id in contact:
        return 2
    return 3


def _base_priority_for_document(doc_id: str) -> int:
    critical_docs = {"aadhaar_card", "land_records", "bank_passbook"}
    if doc_id in critical_docs:
        return 1
    return 3


def generate_action_items(
    scheme_id: str,
    missing_fields: List[str],
    missing_documents: List[str],
    language: str = "hi",
) -> List[Dict]:
    """
    Turn missing fields and documents into user-friendly action items
    with estimated time to complete each.
    """
    actions: List[Dict] = []
    lang_hi = language.startswith("hi")

    # Field-based actions
    for field_id in missing_fields:
        action_id = f"field_{field_id}"
        meta = FIELD_HINTS.get(field_id)
        if not meta:
            title = "एक आवश्यक फ़ील्ड भरें" if lang_hi else "Fill a required field"
            desc = (
                f"फ़ील्ड '{field_id}' फॉर्म में नहीं मिली।"
                if lang_hi
                else f"The field '{field_id}' is missing in the form, please fill it."
            )
        else:
            title = meta["title_hi"] if lang_hi else meta["title_en"]
            desc = meta["hint_hi"] if lang_hi else meta["hint_en"]

        actions.append({
            "action_id": action_id,
            "title": title,
            "description": desc,
            "priority": _base_priority_for_field(field_id),
            "category": "FILL_FIELD",
            "scheme_id": scheme_id,
            "estimated_time": ESTIMATED_TIME.get(action_id, "10 minutes"),
        })

    # Document-based actions
    for doc_id in missing_documents:
        action_id = f"doc_{doc_id}"
        meta = DOCUMENT_HINTS.get(doc_id)
        if not meta:
            title = "आवश्यक दस्तावेज़ अपलोड करें" if lang_hi else "Upload required document"
            desc = (
                f"दस्तावेज़ '{doc_id}' नहीं मिला।"
                if lang_hi
                else f"The document '{doc_id}' is missing, please upload a clear copy."
            )
        else:
            title = meta["title_hi"] if lang_hi else meta["title_en"]
            desc = meta["hint_hi"] if lang_hi else meta["hint_en"]

        actions.append({
            "action_id": action_id,
            "title": title,
            "description": desc,
            "priority": _base_priority_for_document(doc_id),
            "category": "UPLOAD_DOCUMENT",
            "scheme_id": scheme_id,
            "estimated_time": ESTIMATED_TIME.get(action_id, "1-2 days"),
        })

    # Sort: priority asc, fields before documents at same priority
    actions.sort(key=lambda a: (a["priority"], a["category"]))
    return actions

