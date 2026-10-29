"""A shared detector must keep each student's temporal emotion state separate."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from sentio.config import emotion_cfg
from sentio.emotion.detector import EmotionDetector, FaceDetection


@pytest.fixture
def vision():
    cfg = SimpleNamespace(
        CLASSES=list(emotion_cfg.CLASSES),
        IMG_SIZE=emotion_cfg.IMG_SIZE,
        HAAR_CASCADE=emotion_cfg.HAAR_CASCADE,
        FRAME_SKIP=1,
        SMOOTHING_WINDOW=5,
        EMOTION_MIN_CONFIDENCE_THRESHOLD=0.30,
        EMOTION_TO_STATE=dict(emotion_cfg.EMOTION_TO_STATE),
    )
    detector = EmotionDetector(cfg=cfg)
    detector.face_detector = Mock()
    detector.face_detector.detect.return_value = [FaceDetection(8, 8, 32, 32)]
    detector.model = Mock()
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    def predictions(*emotions):
        scores = []
        for emotion in emotions:
            row = np.zeros(len(cfg.CLASSES), dtype=np.float32)
            row[cfg.CLASSES.index(emotion)] = 1.0
            scores.append(SimpleNamespace(numpy=lambda row=row: row[None, :]))
        detector.model.side_effect = scores

    return SimpleNamespace(detector=detector, frame=frame, cfg=cfg, predictions=predictions)


def test_interleaved_sessions_have_independent_smoothed_predictions(vision):
    vision.predictions("happy", "angry", "happy", "angry")

    results = [
        vision.detector.detect_from_frame(vision.frame, session_id=session)
        for session in ("a", "b", "a", "b")
    ]

    assert [result.emotion for result in results] == ["happy", "angry", "happy", "angry"]
    assert [result.confidence for result in results] == pytest.approx([1.0] * 4)


def test_low_confidence_session_cannot_inherit_another_sessions_emotion(vision):
    vision.predictions("happy")
    uncertain = np.full((1, len(vision.cfg.CLASSES)), 1 / len(vision.cfg.CLASSES))
    outputs = list(vision.detector.model.side_effect)
    vision.detector.model.side_effect = outputs + [SimpleNamespace(numpy=lambda: uncertain)]
    first = vision.detector.detect_from_frame(vision.frame, session_id="a")

    second = vision.detector.detect_from_frame(vision.frame, session_id="b")

    assert first.emotion == "happy"
    assert second is None or second.confidence < vision.cfg.EMOTION_MIN_CONFIDENCE_THRESHOLD


def test_frame_skipping_cannot_return_another_sessions_last_result(vision):
    vision.predictions("happy")
    first = vision.detector.detect_from_frame(vision.frame, session_id="a")
    assert first.emotion == "happy"
    vision.cfg.FRAME_SKIP = 2
    vision.detector.face_detector.detect.return_value = []

    assert vision.detector.detect_from_frame(vision.frame, session_id="b") is None
    assert vision.detector.detect_from_frame(vision.frame, session_id="b") is None
    assert vision.detector.detect_from_frame(vision.frame, session_id="b") is None


def test_missing_face_in_one_session_preserves_other_sessions_smoothing(vision):
    vision.predictions("angry", "happy")
    first = vision.detector.detect_from_frame(vision.frame, session_id="b")
    assert first.emotion == "angry"
    vision.detector.face_detector.detect.return_value = []
    assert vision.detector.detect_from_frame(vision.frame, session_id="a") is None
    vision.detector.face_detector.detect.return_value = [FaceDetection(8, 8, 32, 32)]

    second = vision.detector.detect_from_frame(vision.frame, session_id="b")

    assert second.emotion == "angry"
    assert second.confidence == pytest.approx(0.6)
