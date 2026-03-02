import cv2
import numpy as np
from PIL import Image
import io
import structlog

log = structlog.get_logger()


def enhance_image(image_bytes: bytes) -> bytes:
    """
    Full preprocessing pipeline:
    1. Deskew (straighten tilted document)
    2. Denoise
    3. Contrast enhancement (CLAHE)
    Returns enhanced image as bytes
    """
    # Decode bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image")

    log.info("preprocessing.start", shape=img.shape)

    # Step 1: Convert to grayscale for processing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 2: Deskew
    img = _deskew(img, gray)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Step 3: Denoise
    denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Step 4: CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Step 5: Convert back to BGR for OCR compatibility
    result = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    # Encode back to bytes
    _, buffer = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 95])
    log.info("preprocessing.complete")
    return buffer.tobytes()


def _deskew(img: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Detect and correct document skew angle."""
    try:
        # Threshold to find text regions
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Find coordinates of non-zero pixels
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 10:
            return img  # Not enough text to detect skew

        # Get minimum area rectangle
        angle = cv2.minAreaRect(coords)[-1]

        # Normalize angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Only correct if skew > 0.5 degrees
        if abs(angle) < 0.5:
            return img

        # Rotate image
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        log.info("preprocessing.deskew", angle=round(angle, 2))
        return rotated

    except Exception as e:
        log.warning("preprocessing.deskew_failed", error=str(e))
        return img


def assess_quality(image_bytes: bytes) -> dict:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    if img is None:
        return {
            "score": 0,
            "is_acceptable": False,
            "blur_score": 0,
            "brightness": 0,
            "resolution": "unknown",
            "issues": ["Cannot read image"]
        }

    issues = []

    # Blur detection
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    blur_score = min(100, int(laplacian_var / 5))
    if laplacian_var < 100:
        issues.append("Image is too blurry")

    # Brightness check
    mean_brightness = img.mean()
    if mean_brightness < 50:
        issues.append("Image is too dark")
    elif mean_brightness > 220:
        issues.append("Image is overexposed")

    # Resolution check
    h, w = img.shape
    if h < 400 or w < 400:
        issues.append(f"Image resolution too low ({w}x{h}). Minimum 400x400px")

    overall_score = blur_score if not issues else max(0, blur_score - len(issues) * 20)

    return {
        "score": overall_score,
        "is_acceptable": len(issues) == 0 and blur_score > 20,
        "blur_score": blur_score,
        "brightness": round(mean_brightness, 1),
        "resolution": f"{w}x{h}",
        "issues": issues
    }