# BATCH AI Phase 2a (2026-07-20) — defect-photo classifier endpoint.
# Serves the repo-shipped ONNX model (backend/models_ai/defect_classifier_v1.onnx)
# behind ONE authenticated endpoint returning top-1 + top-2 category suggestions.
# Memory-only image handling: the uploaded photo is never persisted anywhere.
# Model-native Hebrew trade classes are returned as-is — mapping to the app
# CATEGORIES enum is deliberately owned by the FE batch.
import io
import json
import logging
import os
import time

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import Image

from contractor_ops.router import get_current_user, get_db
from contractor_ops.upload_rate_limit import (
    check_upload_bytes,
    check_upload_rate_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ai-classify"])

_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models_ai")
_MODEL_PATH = os.path.join(_MODELS_DIR, "defect_classifier_v1.onnx")
_META_PATH = os.path.join(_MODELS_DIR, "defect_classifier_v1.meta.json")

# Classes + version load at module import from meta.json — no fallback values;
# a missing/corrupt meta file must fail loudly at boot, not silently misclassify.
with open(_META_PATH, "r", encoding="utf-8") as _f:
    _META = json.load(_f)
MODEL_VERSION: str = _META["version"]
CLASSES: list[str] = _META["classes"]

MAX_PHOTO_BYTES = 10 * 1024 * 1024  # 10MB cap per spec
LOW_CONFIDENCE_THRESHOLD = 0.55

_session = None


def _get_session():
    """Lazy singleton — the ONNX session loads once per process on the FIRST
    classify call, keeping boot time unchanged."""
    global _session
    if _session is None:
        import onnxruntime as ort
        _session = ort.InferenceSession(_MODEL_PATH, providers=["CPUExecutionProvider"])
    return _session


# ImageNet normalization per the model contract.
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _preprocess(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB").resize((224, 224))
    arr = np.asarray(img, dtype=np.float32) / 255.0          # [224,224,3]
    arr = (arr - _MEAN) / _STD
    arr = arr.transpose(2, 0, 1)[np.newaxis, :]              # [1,3,224,224]
    return arr.astype(np.float32)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - np.max(logits)
    e = np.exp(z)
    return e / e.sum()


@router.post("/classify-defect-photo")
async def classify_defect_photo(
    request: Request,
    photo: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    started = time.monotonic()
    # Same rate-limit mechanism/budget as the task photo upload route.
    check_upload_rate_limit(user["id"])
    # Fast-path 413 on the advertised Content-Length (same pattern as
    # upload_rate_limit.check_content_length, but with this endpoint's 10MB
    # message — the shared helper hardcodes the 50MB wording). The header is
    # spoofable; the post-read check below is the real enforcement.
    try:
        declared = int(request.headers.get("content-length") or 0)
    except (TypeError, ValueError):
        declared = 0
    if declared > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="התמונה גדולה מדי (מקסימום 10MB)")

    data = await photo.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="התמונה גדולה מדי (מקסימום 10MB)")
    check_upload_bytes(user["id"], len(data))

    try:
        tensor = _preprocess(data)
    except Exception:
        raise HTTPException(status_code=422, detail="קובץ התמונה לא תקין")

    try:
        session = _get_session()
        (logits,) = session.run(["logits"], {"image": tensor})
        probs = _softmax(logits[0].astype(np.float64))
        order = np.argsort(probs)[::-1]
        # low_confidence from the RAW top-1 probability (rounding is display-only)
        top1_raw = float(probs[order[0]])
        top = [
            {"category": CLASSES[i], "confidence": round(float(probs[i]), 3)}
            for i in order[:2]
        ]
        low_confidence = top1_raw < LOW_CONFIDENCE_THRESHOLD
    except Exception:
        logger.exception("[AI_CLASSIFY] inference failure")
        raise HTTPException(status_code=503, detail="שירות הזיהוי אינו זמין כרגע")

    latency_ms = int((time.monotonic() - started) * 1000)

    org_id = None
    try:
        db = get_db()
        membership = await db.organization_memberships.find_one(
            {"user_id": user["id"]}, {"_id": 0, "org_id": 1}
        )
        org_id = (membership or {}).get("org_id")
    except Exception:
        pass  # logging metadata only — never fail the request over it

    logger.info(
        "[AI_CLASSIFY] org_id=%s user_id=%s model_version=%s top1=%s confidence=%.3f latency_ms=%d",
        org_id, user["id"], MODEL_VERSION, top[0]["category"], top[0]["confidence"], latency_ms,
    )

    return {
        "model_version": MODEL_VERSION,
        "category": top[0]["category"],
        "confidence": top[0]["confidence"],
        "top2": top,
        "low_confidence": low_confidence,
    }
