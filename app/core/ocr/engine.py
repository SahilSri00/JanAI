import structlog
from openbharatocr import ocr as bharat_ocr
from pathlib import Path
import tempfile, os

log = structlog.get_logger()

CONFIDENCE_THRESHOLD = 0.7


def extract_text(image_bytes: bytes, filename: str = "document.jpg") -> dict:
    """
    Primary OCR using OpenBharatOCR.
    Falls back to PaddleOCR if confidence < threshold.
    
    Returns:
        {
            "text": str,
            "confidence": float,
            "engine_used": str,
            "blocks": list
        }
    """
    # Write bytes to temp file (OpenBharatOCR needs file path)
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        log.info("ocr.start", engine="openbharatocr", file=filename)
        result = _run_openbharat(tmp_path)

        if result["confidence"] >= CONFIDENCE_THRESHOLD:
            log.info("ocr.complete", engine="openbharatocr",
                     confidence=result["confidence"])
            return result

        # Confidence too low — try PaddleOCR
        log.warning("ocr.low_confidence", confidence=result["confidence"],
                    threshold=CONFIDENCE_THRESHOLD, fallback="paddleocr")
        paddle_result = _run_paddle(tmp_path)

        # Return whichever got higher confidence
        if paddle_result["confidence"] > result["confidence"]:
            log.info("ocr.fallback_better", engine="paddleocr",
                     confidence=paddle_result["confidence"])
            return paddle_result

        return result

    finally:
        os.unlink(tmp_path)  # Always clean up temp file


def _run_openbharat(file_path: str) -> dict:
    """Run OpenBharatOCR and normalize output."""
    try:
        from openbharatocr.ocr import aadhaar, pan, passport
        from PIL import Image
        
        # Try PAN card extraction first
        try:
            raw = pan(file_path)
        except:
            raw = {}

        all_text = []
        blocks = []
        for field_name, field_value in raw.items():
            if field_value and isinstance(field_value, str) and field_value.strip():
                all_text.append(f"{field_name}: {field_value}")
                blocks.append({
                    "field": field_name,
                    "text": field_value,
                    "confidence": 0.9
                })

        if not blocks:
            # Fall through to PaddleOCR
            return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr",
                    "blocks": [], "structured_fields": {}}

        return {
            "text": "\n".join(all_text),
            "confidence": 0.9,
            "engine_used": "openbharatocr",
            "blocks": blocks,
            "structured_fields": raw
        }

    except Exception as e:
        log.error("ocr.openbharat_failed", error=str(e))
        return {"text": "", "confidence": 0.0, "engine_used": "openbharatocr",
                "blocks": [], "error": str(e)}

def _run_paddle(file_path: str) -> dict:
    """Fallback OCR using EasyOCR (replacing PaddleOCR due to compatibility issues)."""
    try:
        import easyocr
        reader = easyocr.Reader(['en', 'hi'], gpu=False)
        raw = reader.readtext(file_path)

        blocks = []
        all_text = []
        total_confidence = 0.0

        for (bbox, text, conf) in raw:
            if text.strip():
                blocks.append({
                    "text": text,
                    "confidence": float(conf),
                    "bbox": str(bbox)
                })
                all_text.append(text)
                total_confidence += float(conf)

        avg_confidence = total_confidence / len(blocks) if blocks else 0.0

        return {
            "text": "\n".join(all_text),
            "confidence": avg_confidence,
            "engine_used": "easyocr",
            "blocks": blocks
        }

    except Exception as e:
        log.error("ocr.easyocr_failed", error=str(e))
        return {"text": "", "confidence": 0.0, "engine_used": "easyocr",
                "blocks": [], "error": str(e)}
        
        
# def _run_paddle(file_path: str) -> dict:
#     """Run PaddleOCR and normalize output."""
#     try:
#         # Disable PIR (Parallel Intermediate Representation) to avoid
#         # Unimplemented errors with PaddlePaddle 3.x
#         import paddle
#         paddle.set_flags({'FLAGS_enable_pir_api': False, 'FLAGS_enable_pir_in_executor': False})
        
#         from paddleocr import PaddleOCR
#         paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
#         raw = paddle_ocr.predict(file_path)
        
#         blocks = []
#         all_text = []
#         total_confidence = 0.0

#         if raw:
#             for result in raw:
#                 # PaddleOCR 3.x returns result differently
#                 rec_texts = result.get('rec_texts', [])
#                 rec_scores = result.get('rec_scores', [])
                
#                 for text, conf in zip(rec_texts, rec_scores):
#                     if text.strip():
#                         blocks.append({
#                             "text": text,
#                             "confidence": float(conf),
#                         })
#                         all_text.append(text)
#                         total_confidence += float(conf)

#         avg_confidence = total_confidence / len(blocks) if blocks else 0.0

#         return {
#             "text": "\n".join(all_text),
#             "confidence": avg_confidence,
#             "engine_used": "paddleocr",
#             "blocks": blocks
#         }

#     except Exception as e:
#         log.error("ocr.paddle_failed", error=str(e))
#         return {"text": "", "confidence": 0.0, "engine_used": "paddleocr",
#                 "blocks": [], "error": str(e)}