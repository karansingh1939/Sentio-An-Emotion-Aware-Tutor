"""
emotion_detector.py — Computer Vision Pipeline for Emotion Detection
=====================================================================
Responsibilities:
  1. Build / load a CNN model for 7-class facial emotion recognition
  2. Detect faces in frames using OpenCV Haar Cascades
  3. Run real-time inference on webcam or single frames
  4. Smooth predictions over a sliding window to avoid jitter
  5. Map raw emotions → pedagogical learning states

Architecture (custom_cnn):
  Input 48×48×1
  → [Conv→BN→ReLU→Conv→BN→ReLU→MaxPool→Dropout] × 3 blocks
  → GlobalAveragePooling
  → Dense(256) → BN → ReLU → Dropout
  → Dense(7, softmax)

Usage:
    detector = EmotionDetector()
    detector.load_model()                        # or .build_model() + .train()

    # Single frame
    result = detector.detect_from_frame(frame)   # BGR numpy array

    # Live webcam loop
    detector.run_webcam_loop(callback=my_fn)
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np
import tensorflow as tf

# ---------------------------------------------------------------------------
# Keras compatibility shim
# TensorFlow < 2.16  : keras lives inside tensorflow  -> use tf.keras
# TensorFlow >= 2.16 : keras is a standalone package  -> import keras directly
# This block handles both cases automatically.
# ---------------------------------------------------------------------------
try:
    import keras
    from keras import Model, layers, regularizers
    from keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau, TensorBoard
except ImportError:
    from tensorflow import keras
    from tensorflow.keras import Model, layers, regularizers
    from tensorflow.keras.callbacks import (
        EarlyStopping,
        ModelCheckpoint,
        ReduceLROnPlateau,
        TensorBoard,
    )

from sentio.config import CHECKPOINT_DIR, LOG_DIR, emotion_cfg

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────


@dataclass
class FaceDetection:
    """Bounding box for a single detected face."""

    x: int
    y: int
    w: int
    h: int

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        """Returns (x1, y1, x2, y2) for slicing."""
        return self.x, self.y, self.x + self.w, self.y + self.h


@dataclass
class EmotionResult:
    """Full result for one frame's dominant face."""

    emotion: str  # e.g. "happy"
    confidence: float  # 0.0 – 1.0
    learning_state: str  # e.g. "engaged"
    all_scores: dict = field(default_factory=dict)  # {emotion: score}
    face: Optional[FaceDetection] = None
    is_smoothed: bool = False

    @property
    def is_confident(self) -> bool:
        from sentio.config import tutor_cfg

        return self.confidence >= tutor_cfg.EMOTION_CONFIDENCE_THRESHOLD

    def __str__(self):
        return f"[{self.emotion.upper()}] conf={self.confidence:.2f} state={self.learning_state}"


# ─────────────────────────────────────────────
# CNN MODEL BUILDER
# ─────────────────────────────────────────────


class EmotionModelBuilder:
    """
    Builds the CNN architecture for emotion recognition.
    Supports three backbones: custom_cnn, mobilenet, resnet.
    """

    def __init__(self, cfg=emotion_cfg):
        self.cfg = cfg

    def build(self) -> Model:
        backbone = self.cfg.BACKBONE
        logger.info(f"Building model with backbone: {backbone}")

        if backbone == "custom_cnn":
            return self._build_custom_cnn()
        elif backbone == "mobilenet":
            return self._build_mobilenet()
        elif backbone == "resnet":
            return self._build_resnet()
        else:
            raise ValueError(f"Unknown backbone: {backbone}")

    # ── Custom CNN ─────────────────────────────
    def _build_custom_cnn(self) -> Model:
        """
        Deep CNN inspired by VGGNet-style blocks.
        Designed for 48×48 grayscale input (FER2013).
        """
        inp = keras.Input(shape=self.cfg.INPUT_SHAPE, name="face_input")

        # ── Block 1: 64 filters
        x = self._conv_block(inp, filters=64, block_name="block1")
        x = layers.MaxPooling2D((2, 2), name="pool1")(x)
        x = layers.Dropout(0.25, name="drop1")(x)

        # ── Block 2: 128 filters
        x = self._conv_block(x, filters=128, block_name="block2")
        x = layers.MaxPooling2D((2, 2), name="pool2")(x)
        x = layers.Dropout(0.25, name="drop2")(x)

        # ── Block 3: 256 filters
        x = self._conv_block(x, filters=256, block_name="block3")
        x = layers.MaxPooling2D((2, 2), name="pool3")(x)
        x = layers.Dropout(0.25, name="drop3")(x)

        # ── Block 4: 512 filters
        x = self._conv_block(x, filters=512, block_name="block4")
        x = layers.GlobalAveragePooling2D(name="gap")(x)

        # ── Classifier head
        x = layers.Dense(256, kernel_regularizer=regularizers.l2(1e-4), name="fc1")(x)
        x = layers.BatchNormalization(name="bn_fc1")(x)
        x = layers.Activation("relu", name="relu_fc1")(x)
        x = layers.Dropout(0.5, name="drop_fc1")(x)

        out = layers.Dense(self.cfg.NUM_CLASSES, activation="softmax", name="emotion_output")(x)

        model = Model(inputs=inp, outputs=out, name="EmotionCNN")
        return model

    def _conv_block(self, x, filters: int, block_name: str):
        """Two Conv2D layers with BN + ReLU (VGG-style)."""
        x = layers.Conv2D(
            filters,
            (3, 3),
            padding="same",
            kernel_regularizer=regularizers.l2(1e-4),
            name=f"{block_name}_conv1",
        )(x)
        x = layers.BatchNormalization(name=f"{block_name}_bn1")(x)
        x = layers.Activation("relu", name=f"{block_name}_relu1")(x)

        x = layers.Conv2D(
            filters,
            (3, 3),
            padding="same",
            kernel_regularizer=regularizers.l2(1e-4),
            name=f"{block_name}_conv2",
        )(x)
        x = layers.BatchNormalization(name=f"{block_name}_bn2")(x)
        x = layers.Activation("relu", name=f"{block_name}_relu2")(x)
        return x

    # ── MobileNetV2 Transfer Learning ──────────
    def _build_mobilenet(self) -> Model:
        """
        MobileNetV2 transfer learning.
        Converts grayscale → RGB by repeating channels.
        """
        # FER2013 is grayscale; MobileNet expects RGB
        inp = keras.Input(shape=self.cfg.INPUT_SHAPE, name="face_input")
        x = layers.Lambda(lambda t: tf.repeat(t, 3, axis=-1), name="gray_to_rgb")(inp)
        x = layers.Resizing(96, 96, name="resize_96")(x)  # MobileNet min size

        base = keras.applications.MobileNetV2(
            input_shape=(96, 96, 3), include_top=False, weights="imagenet"
        )
        base.trainable = False  # Freeze initially; unfreeze top layers later

        x = base(x, training=False)
        x = layers.GlobalAveragePooling2D(name="gap")(x)
        x = layers.Dense(128, activation="relu", name="fc1")(x)
        x = layers.Dropout(0.4, name="drop_fc1")(x)
        out = layers.Dense(self.cfg.NUM_CLASSES, activation="softmax", name="emotion_output")(x)

        return Model(inputs=inp, outputs=out, name="EmotionMobileNet")

    # ── ResNet50 Transfer Learning ──────────────
    def _build_resnet(self) -> Model:
        inp = keras.Input(shape=self.cfg.INPUT_SHAPE, name="face_input")
        x = layers.Lambda(lambda t: tf.repeat(t, 3, axis=-1), name="gray_to_rgb")(inp)
        x = layers.Resizing(64, 64, name="resize_64")(x)

        base = keras.applications.ResNet50(
            input_shape=(64, 64, 3), include_top=False, weights="imagenet"
        )
        base.trainable = False

        x = base(x, training=False)
        x = layers.GlobalAveragePooling2D(name="gap")(x)
        x = layers.Dense(256, activation="relu", name="fc1")(x)
        x = layers.Dropout(0.5, name="drop_fc1")(x)
        out = layers.Dense(self.cfg.NUM_CLASSES, activation="softmax", name="emotion_output")(x)

        return Model(inputs=inp, outputs=out, name="EmotionResNet")


# ─────────────────────────────────────────────
# FACE DETECTOR
# ─────────────────────────────────────────────


class FaceDetector:
    """
    Wraps OpenCV Haar Cascade for fast face detection.
    Falls back gracefully if cascade file is missing.
    """

    def __init__(self, cfg=emotion_cfg):
        self.cfg = cfg
        try:
            cascade_path = cv2.data.haarcascades + cfg.HAAR_CASCADE
            self.cascade = cv2.CascadeClassifier(cascade_path)
            if self.cascade.empty():
                logger.warning(
                    f"Failed to load Haar cascade from {cascade_path}. "
                    "Emotion detection face classifier is empty."
                )
                self.cascade = None
            else:
                logger.info("Haar Cascade face detector loaded.")
        except Exception as e:
            logger.warning(
                f"Error loading face detector cascade: {e}. Face detection will be disabled."
            )
            self.cascade = None

    def detect(self, gray_frame: np.ndarray) -> List[FaceDetection]:
        """
        Detect faces in a grayscale frame.

        Args:
            gray_frame: Grayscale uint8 numpy array (H*W)

        Returns:
            List of FaceDetection objects, sorted largest-first
        """
        if not self.cascade:
            return []
        faces_raw = self.cascade.detectMultiScale(
            gray_frame,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        if len(faces_raw) == 0:
            return []

        detections = [FaceDetection(x, y, w, h) for (x, y, w, h) in faces_raw]
        # Sort by area descending (largest = likely primary subject)
        detections.sort(key=lambda d: d.w * d.h, reverse=True)
        return detections


# ─────────────────────────────────────────────
# EMOTION SMOOTHER
# ─────────────────────────────────────────────


class EmotionSmoother:
    """
    Temporal smoothing using a sliding window of raw score vectors.
    Averages the last N softmax outputs to reduce per-frame jitter.
    """

    def __init__(self, window_size: int = emotion_cfg.SMOOTHING_WINDOW):
        self.window_size = window_size
        self._buffer: deque = deque(maxlen=window_size)

    def update(self, scores: np.ndarray) -> np.ndarray:
        """
        Push new scores and return EMA smoothed scores.

        Args:
            scores: np.ndarray of shape (num_classes,)

        Returns:
            Smoothed scores of same shape
        """
        if not self._buffer:
            smoothed = scores
        else:
            alpha = 0.4
            smoothed = alpha * scores + (1.0 - alpha) * self._buffer[-1]
        self._buffer.append(smoothed)
        return smoothed

    def reset(self):
        self._buffer.clear()

    @property
    def is_warm(self) -> bool:
        """True once buffer has enough frames."""
        return len(self._buffer) >= self.window_size // 2


# ─────────────────────────────────────────────
# MAIN EMOTION DETECTOR
# ─────────────────────────────────────────────


class EmotionDetector:
    """
    End-to-end emotion detection pipeline.

    Workflow:
        frame (BGR) → grayscale → face detection → crop & resize
        → CNN inference → softmax smoothing → EmotionResult

    Example:
        detector = EmotionDetector()
        detector.load_model()
        result = detector.detect_from_frame(frame)
        print(result.emotion, result.learning_state)
    """

    def __init__(self, cfg=emotion_cfg):
        self.cfg = cfg
        self.model: Optional[Model] = None
        from threading import RLock

        self._streams = {}
        self._inference_lock = RLock()
        self.face_detector = FaceDetector(cfg)
        self.smoother = EmotionSmoother(cfg.SMOOTHING_WINDOW)
        self._frame_count = 0
        self._last_result: Optional[EmotionResult] = None

    # ── Model Management ───────────────────────

    def build_model(self) -> Model:
        """Build model from scratch and compile it."""
        builder = EmotionModelBuilder(self.cfg)
        self.model = builder.build()
        self._compile()
        logger.info(f"Model built: {self.model.name}")
        self.model.summary(print_fn=logger.debug)
        return self.model

    def _compile(self):
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.cfg.LEARNING_RATE),
            loss="categorical_crossentropy",
            metrics=["accuracy", keras.metrics.TopKCategoricalAccuracy(k=2, name="top2_acc")],
        )

    def save_model(self, path: Optional[Path] = None):
        path = path or self.cfg.MODEL_PATH
        self.model.save(str(path))
        logger.info(f"Model saved → {path}")

    def load_model(self, path: Optional[Path] = None):
        """Load trained weights; disable inference if weights are unavailable."""
        path = path or self.cfg.MODEL_PATH
        try:
            if Path(path).exists():
                print("Loading model from:", path)
                self.model = keras.models.load_model(str(path), compile=False)
                logger.info(f"Model loaded from {path}")
            else:
                logger.warning(
                    f"No saved model at {path}. Emotion inference is disabled. "
                    "Train or restore the model to enable it."
                )
                self.model = None
        except Exception as e:
            logger.error(
                f"Failed to load or build emotion model: {e}. Emotion detection will be disabled."
            )
            self.model = None

    def get_callbacks(self) -> list:
        """Standard training callbacks."""
        return [
            ModelCheckpoint(
                filepath=str(
                    CHECKPOINT_DIR / "emotion_epoch{epoch:02d}_val{val_accuracy:.4f}.weights.h5"
                ),
                monitor="val_accuracy",
                save_best_only=True,
                save_weights_only=True,
                verbose=1,
            ),
            EarlyStopping(
                monitor="val_accuracy",
                patience=self.cfg.EARLY_STOP_PATIENCE,
                restore_best_weights=True,
                verbose=1,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=self.cfg.LR_DECAY_FACTOR,
                patience=self.cfg.LR_PATIENCE,
                min_lr=1e-6,
                verbose=1,
            ),
            TensorBoard(log_dir=str(LOG_DIR / "tensorboard"), histogram_freq=1),
        ]

    # ── Preprocessing ──────────────────────────

    def preprocess_face(self, face_roi: np.ndarray) -> np.ndarray:
        """
        Prepare a face ROI for CNN inference.

        Steps:
            1. Convert to grayscale (if BGR)
            2. Resize to IMG_SIZE × IMG_SIZE
            3. Normalize to [0, 1]
            4. Expand dims → (1, H, W, 1)
        """
        if face_roi.ndim == 3 and face_roi.shape[2] == 3:
            face_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

        resized = cv2.resize(
            face_roi, (self.cfg.IMG_SIZE, self.cfg.IMG_SIZE), interpolation=cv2.INTER_AREA
        )
        normalized = resized.astype("float32") / 255.0
        # Shape: (1, 48, 48, 1)
        return np.expand_dims(np.expand_dims(normalized, -1), 0)

    # ── Inference ──────────────────────────────

    def predict_emotion(self, face_roi: np.ndarray, smooth: bool = True) -> Tuple[str, float, dict]:
        """
        Run CNN inference on a single face ROI.

        Args:
            face_roi: Cropped face image (BGR or grayscale)
            smooth:   Apply temporal smoothing

        Returns:
            (emotion_label, confidence, all_scores_dict)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        preprocessed = self.preprocess_face(face_roi)
        raw_scores = self.model(preprocessed, training=False).numpy()[0]  # (7,)

        if smooth:
            scores = self.smoother.update(raw_scores)
        else:
            scores = raw_scores

        idx = int(np.argmax(scores))
        emotion = self.cfg.CLASSES[idx]
        confidence = float(scores[idx])
        all_scores = {cls: float(scores[i]) for i, cls in enumerate(self.cfg.CLASSES)}

        return emotion, confidence, all_scores

    def detect_from_frame(
        self, frame: np.ndarray, session_id: Optional[str] = None
    ) -> Optional[EmotionResult]:
        """Share model weights while keeping prediction history per session."""
        from copy import copy

        with self._inference_lock:
            detector = self
            if session_id:
                if session_id not in self._streams:
                    detector = copy(self)
                    detector.smoother = EmotionSmoother(self.cfg.SMOOTHING_WINDOW)
                    detector._frame_count = 0
                    detector._last_result = None
                    self._streams[session_id] = detector
                detector = self._streams[session_id]
                detector.model = self.model
            return detector._detect_from_frame(frame)

    def clear_session(self, session_id):
        with self._inference_lock:
            self._streams.pop(session_id, None)

    def _detect_from_frame(self, frame: np.ndarray) -> Optional[EmotionResult]:
        """
        Full pipeline: BGR frame → EmotionResult for the primary face.

        Args:
            frame: BGR uint8 numpy array from cv2.VideoCapture

        Returns:
            EmotionResult or None if no face detected
        """
        self._frame_count += 1

        # Frame skipping for performance
        if self._frame_count % self.cfg.FRAME_SKIP != 0:
            return self._last_result

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_detector.detect(gray)

        if not faces:
            self.smoother.reset()
            self._last_result = None
            return None

        # Use the largest face (primary subject)
        primary = faces[0]
        x, y, w, h = primary.x, primary.y, primary.w, primary.h

        # Add 10% padding margin around the bounding box
        h_pad = int(h * 0.10)
        w_pad = int(w * 0.10)
        y1 = max(0, y - h_pad)
        y2 = min(frame.shape[0], y + h + h_pad)
        x1 = max(0, x - w_pad)
        x2 = min(frame.shape[1], x + w + w_pad)

        face_roi = frame[y1:y2, x1:x2]

        if face_roi.size == 0:
            return None

        if self.model is None:
            logger.warning("Emotion model is not available. Skipping emotion prediction.")
            return None

        emotion, confidence, all_scores = self.predict_emotion(face_roi, smooth=True)

        # Low-confidence predictions check:
        # Reuse last prediction if confidence is below threshold to avoid rapid flickering.
        min_threshold = getattr(self.cfg, "EMOTION_MIN_CONFIDENCE_THRESHOLD", 0.30)
        if confidence < min_threshold and self._last_result is not None:
            emotion = self._last_result.emotion
            confidence = self._last_result.confidence
            all_scores = self._last_result.all_scores

        learning_state = self.cfg.EMOTION_TO_STATE.get(emotion, "neutral")

        result = EmotionResult(
            emotion=emotion,
            confidence=confidence,
            learning_state=learning_state,
            all_scores=all_scores,
            face=primary,
            is_smoothed=True,
        )

        self._last_result = result
        return result

    def detect_batch(self, frames: List[np.ndarray]) -> List[Optional[EmotionResult]]:
        """
        Run detection on a list of frames (e.g. for video analysis).
        """
        return [self.detect_from_frame(f) for f in frames]

    # ── Webcam Loop ────────────────────────────

    def run_webcam_loop(
        self, callback: Optional[Callable[[EmotionResult], None]] = None, display: bool = True
    ):
        """
        Start a live webcam loop. Runs until 'q' is pressed.

        Args:
            callback: Called with each EmotionResult (use to feed tutor agent)
            display:  Whether to show annotated video window
        """
        cap = cv2.VideoCapture(self.cfg.WEBCAM_INDEX)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open webcam at index {self.cfg.WEBCAM_INDEX}")
        logger.info("Webcam loop started. Press 'q' to quit.")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to read frame from webcam.")
                    break

                result = self.detect_from_frame(frame)

                if result and callback:
                    callback(result)

                if display:
                    annotated = self._annotate_frame(frame, result)
                    cv2.imshow("Emotion-Aware Tutor — Face Cam", annotated)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            cap.release()
            if display:
                cv2.destroyAllWindows()
            logger.info("Webcam loop ended.")

    # ── Annotation ─────────────────────────────

    def _annotate_frame(self, frame: np.ndarray, result: Optional[EmotionResult]) -> np.ndarray:
        """
        Draw face bounding box + emotion label on frame.
        Returns annotated copy.
        """
        out = frame.copy()

        if result is None:
            cv2.putText(
                out, "No face detected", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2
            )
            return out

        # State → color mapping
        state_colors = {
            "engaged": (0, 200, 0),
            "curious": (0, 200, 200),
            "neutral": (180, 180, 180),
            "struggling": (0, 100, 255),
            "anxious": (0, 165, 255),
            "frustrated": (0, 0, 255),
            "disengaged": (100, 100, 100),
        }
        color = state_colors.get(result.learning_state, (255, 255, 255))

        # Face bounding box
        if result.face:
            f = result.face
            cv2.rectangle(out, (f.x, f.y), (f.x + f.w, f.y + f.h), color, 2)

        # Emotion + confidence label
        label = f"{result.emotion} ({result.confidence:.0%})"
        cv2.putText(out, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

        # Learning state badge
        state_label = f"State: {result.learning_state.upper()}"
        cv2.putText(out, state_label, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Mini score bar chart (bottom of frame)
        self._draw_score_bars(out, result.all_scores)

        return out

    def _draw_score_bars(self, frame: np.ndarray, scores: dict):
        """Draw small horizontal bars for all emotion scores."""
        h, w = frame.shape[:2]
        bar_h = 12
        bar_max_w = 120
        start_y = h - (len(scores) * (bar_h + 4)) - 10
        start_x = 10

        for i, (emotion, score) in enumerate(scores.items()):
            y = start_y + i * (bar_h + 4)
            bar_w = int(score * bar_max_w)
            cv2.rectangle(frame, (start_x, y), (start_x + bar_w, y + bar_h), (80, 200, 120), -1)
            cv2.putText(
                frame,
                f"{emotion[:3]} {score:.2f}",
                (start_x + bar_max_w + 5, y + bar_h - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (220, 220, 220),
                1,
            )

    # ── Utility ────────────────────────────────

    def reset(self):
        """Reset frame counter and smoother (e.g. on new session)."""
        self._frame_count = 0
        self._last_result = None
        self.smoother.reset()

    @property
    def is_ready(self) -> bool:
        return self.model is not None


# ─────────────────────────────────────────────
# QUICK SMOKE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    detector = EmotionDetector()
    detector.load_model()

    print(f"Model ready: {detector.is_ready}")
    print(f"Classes: {emotion_cfg.CLASSES}")
    print(f"Backbone: {emotion_cfg.BACKBONE}")

    # Test with a blank frame (expect low-confidence result)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect_from_frame(dummy_frame)
    print(f"Dummy frame result: {result}")

    # Uncomment to test live webcam
    # detector.run_webcam_loop(display=True)
