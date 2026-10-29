"""Who may send camera data, and how much of it the server will decode."""

import base64
import binascii
import json
import logging
from io import BytesIO

import numpy as np
from fastapi import HTTPException

from sentio.config import emotion_cfg

logger = logging.getLogger(__name__)


def emotion_enabled():
    return emotion_cfg.ENABLED


def camera_consented(persister, owner):
    """The learner's most recent consent record must allow camera telemetry."""
    history = persister.auth_repo.get_consent_history(owner)
    if not history:
        return False
    try:
        preferences = json.loads(history[0]["preferences_json"])
    except (TypeError, ValueError):
        return False
    return bool(preferences.get("telemetry"))


def require_emotion_access(persister, owner):
    if not emotion_enabled():
        raise HTTPException(404, "Emotion detection is not enabled on this installation.")
    if not camera_consented(persister, owner):
        raise HTTPException(403, "Turn on camera consent in Settings before sharing camera data.")


def decode_frame(frame_b64):
    """Decode a bounded base64 JPEG/PNG into a BGR array, or None if unusable.

    Size and pixel limits are checked before full decoding, so an oversized or
    decompression-bomb image is rejected without allocating its pixels.
    """
    if not frame_b64 or len(frame_b64) > emotion_cfg.MAX_FRAME_BYTES * 4 // 3 + 4:
        return None
    try:
        raw = base64.b64decode(frame_b64, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        from PIL import Image

        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
        if width * height > emotion_cfg.MAX_FRAME_PIXELS:
            return None
        import cv2

        return cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception as exc:
        logger.warning("Frame decode failed: %s", type(exc).__name__)
        return None
