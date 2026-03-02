import cv2
import numpy as np
import structlog

log = structlog.get_logger()

UPSCALE_THRESHOLD = 1200  # Upscale if max dimension < 1200px


def assess_quality(image_bytes: bytes) -> dict:
    """
    Lightweight image quality check for OCR suitability.
    Returns a dict used by `app/api/upload.py` for logging and early rejection.
    """
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Blur score: variance of Laplacian (higher = sharper)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Brightness: mean grayscale intensity (0-255)
        brightness = float(gray.mean())

        issues = []
        if max(h, w) < 600:
            issues.append("low_resolution")
        if blur_score < 30:
            issues.append("blurry")
        if brightness < 60:
            issues.append("too_dark")
        if brightness > 220:
            issues.append("too_bright")

        # Score: base it on sharpness, then apply penalties
        score = int(max(0, min(100, blur_score)))
        if "low_resolution" in issues:
            score = max(0, score - 15)
        if "too_dark" in issues or "too_bright" in issues:
            score = max(0, score - 15)
        if "blurry" in issues:
            score = max(0, score - 25)

        is_acceptable = score >= 30

        return {
            "blur_score": int(round(blur_score)),
            "brightness": round(brightness, 1),
            "resolution": f"{w}x{h}",
            "score": score,
            "is_acceptable": is_acceptable,
            "issues": issues,
        }
    except Exception as e:
        log.exception("quality_assessment_failed", error=str(e))
        return {
            "blur_score": 0,
            "brightness": 0.0,
            "resolution": "0x0",
            "score": 0,
            "is_acceptable": False,
            "issues": ["decode_failed"],
        }


def enhance_image(image_bytes: bytes) -> bytes:
    """
    Optimized preprocessing for ID documents:
    1. Decode
    2. Upscale small images
    3. Mild denoise
    4. Contrast enhancement (adaptive)
    5. Safe deskew (only if strong skew)
    """

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image")

    log.info("preprocessing.start", shape=img.shape)

    h, w = img.shape[:2]

    # 1️⃣ Adaptive upscale
    max_dim = max(h, w)
    if max_dim < UPSCALE_THRESHOLD:
        scale = UPSCALE_THRESHOLD / max_dim
        img = cv2.resize(
            img,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )
        log.info("preprocessing.upscaled", scale=round(scale, 2))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2️⃣ Edge-preserving denoise
    gray = cv2.medianBlur(gray, 3)

    # 3️⃣ Contrast-based CLAHE trigger
    contrast = gray.std()
    if contrast < 50:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        log.info("preprocessing.clahe_applied")

    # 4️⃣ Safe deskew
    gray = _safe_deskew(gray)

    result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    _, buffer = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 95])

    log.info("preprocessing.complete")
    return buffer.tobytes()

def _safe_deskew(gray: np.ndarray) -> np.ndarray:
    """
    Safer skew detection using Hough transform.
    Only rotates if angle > 2 degrees.
    """

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

    if lines is None:
        return gray

    angles = []

    for rho, theta in lines[:20]:
        angle = (theta - np.pi / 2) * (180 / np.pi)
        angles.append(angle)

    if not angles:
        return gray

    median_angle = np.median(angles)

    if abs(median_angle) < 2.0:
        return gray

    h, w = gray.shape
    center = (w // 2, h // 2)

    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        gray,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    log.info("preprocessing.deskew", angle=round(float(median_angle), 2))

    return rotated