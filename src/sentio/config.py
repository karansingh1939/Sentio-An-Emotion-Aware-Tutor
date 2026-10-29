"""
config.py — Central Configuration for Emotion-Aware AI Tutor
=============================================================
All hyperparameters, paths, model settings, and system-wide constants
live here. Every other module imports from this file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ─────────────────────────────────────────────
# PROJECT PATHS
# ─────────────────────────────────────────────
PACKAGE_DIR = Path(__file__).resolve().parent
_checkout = PACKAGE_DIR.parent.parent
_default_home = _checkout if (_checkout / "pyproject.toml").exists() else Path.home() / ".sentio"
BASE_DIR = Path(os.getenv("SENTIO_HOME", _default_home)).expanduser().resolve()
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"

# Create directories if they don't exist
for directory in [
    DATA_DIR,
    MODEL_DIR,
    LOG_DIR,
    CHECKPOINT_DIR,
    LOG_DIR / "sessions",
    LOG_DIR / "emotions",
    BASE_DIR / "prompts",
]:
    directory.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# EMOTION DETECTION (Computer Vision)
# ─────────────────────────────────────────────
class EmotionConfig:
    # Emotion classes the model can detect
    CLASSES = [
        "angry",
        "disgusted",
        "fearful",
        "happy",
        "sad",
        "surprised",
        "neutral",
    ]
    NUM_CLASSES = len(CLASSES)

    # Input image settings
    IMG_SIZE = 48  # FER2013 standard: 48x48 grayscale
    IMG_CHANNELS = 1  # Grayscale
    INPUT_SHAPE = (IMG_SIZE, IMG_SIZE, IMG_CHANNELS)

    # CNN Training hyperparameters
    BATCH_SIZE = 64
    EPOCHS = 50
    LEARNING_RATE = 1e-3
    LR_DECAY_FACTOR = 0.5
    LR_PATIENCE = 5  # Epochs before reducing LR
    EARLY_STOP_PATIENCE = 10

    # Data augmentation
    ROTATION_RANGE = 15
    WIDTH_SHIFT = 0.1
    HEIGHT_SHIFT = 0.1
    HORIZONTAL_FLIP = True
    ZOOM_RANGE = 0.1

    # Pretrained model options: "custom_cnn" | "mobilenet" | "resnet"
    BACKBONE = "custom_cnn"

    # Saved model paths
    MODEL_PATH = MODEL_DIR / "emotion_model.h5"
    WEIGHTS_PATH = MODEL_DIR / "emotion_weights.weights.h5"

    # Webcam
    WEBCAM_INDEX = 0
    FACE_DETECTION_CONFIDENCE = 0.5
    FRAME_SKIP = 1  # Process every Nth frame (performance)

    # Haar Cascade for face detection (OpenCV built-in)
    HAAR_CASCADE = "haarcascade_frontalface_default.xml"

    # Emotion → Learning State mapping
    # Maps raw emotions to pedagogical states
    EMOTION_TO_STATE = {
        "happy": "engaged",
        "neutral": "neutral",
        "surprised": "curious",
        "sad": "struggling",
        "fearful": "anxious",
        "angry": "frustrated",
        "disgusted": "disengaged",
    }

    # Smoothing window: average over last N frames to avoid jitter
    SMOOTHING_WINDOW = 5
    EMOTION_MIN_CONFIDENCE_THRESHOLD = 0.30


# ─────────────────────────────────────────────
# NLP / LANGUAGE MODEL
# ─────────────────────────────────────────────
class NLPConfig:
    # Local Ollama model used for every generation
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

    # Qdrant Vector Database Mode: "local" (disk persistent) | "memory" (ephemeral) | "server" (external container)
    QDRANT_MODE = os.getenv("QDRANT_MODE", "local").lower().strip()
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_PATH = DATA_DIR / "qdrant_db"

    # Sentence embedding model (for semantic similarity / RAG)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Context window: how many past exchanges to include
    MAX_HISTORY_TURNS = 6

    # Prompt template path
    PROMPT_TEMPLATE_DIR = BASE_DIR / "prompts"


# ─────────────────────────────────────────────
# TUTORING & PEDAGOGY
# ─────────────────────────────────────────────
class TutorConfig:
    # Supported subjects
    SUBJECTS = [
        "mathematics",
        "physics",
        "chemistry",
        "biology",
        "computer_science",
        "history",
        "literature",
    ]

    # Difficulty levels
    DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]

    # Teaching strategies mapped to learning states
    # Each state triggers a different pedagogical approach
    STRATEGY_MAP = {
        "engaged": "challenge",  # Push harder, introduce new concepts
        "neutral": "standard",  # Normal pacing
        "curious": "explore",  # Deep-dive, show connections
        "struggling": "simplify",  # Break it down, use analogies
        "anxious": "reassure",  # Encouragement + small wins
        "frustrated": "reframe",  # Try a different explanation angle
        "disengaged": "motivate",  # Use real-world examples, gamify
    }

    # How long (seconds) a state must persist before adapting
    STATE_PERSISTENCE_THRESHOLD = 5

    # Minimum confidence to act on an emotion detection
    EMOTION_CONFIDENCE_THRESHOLD = 0.6

    # Session settings
    MAX_SESSION_DURATION_MIN = 90
    IDLE_TIMEOUT_SEC = 300

    # Feedback loop: re-assess comprehension every N exchanges
    COMPREHENSION_CHECK_INTERVAL = 5
    ENABLE_ADAPTIVE_TUTORING = True


# ─────────────────────────────────────────────
# SESSION & LOGGING
# ─────────────────────────────────────────────
class SessionConfig:
    SESSION_LOG_PATH = LOG_DIR / "sessions"
    EMOTION_LOG_PATH = LOG_DIR / "emotions"
    MAX_SESSIONS_STORED = 100

    # Database (SQLite for local, change to postgres URI for prod)
    DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/tutor_sessions.db")


KNOWN_INSECURE_SECRETS = {
    "sentio_super_secure_secret_key_12345!",
    "secret",
    "dev_secret",
    "change_me",
    "123456",
    "password",
    "default_secret",
}


class APIConfig:
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    RELOAD = os.getenv("RELOAD", "False").lower() in ("true", "1", "yes")
    API_PREFIX = "/api/v1"

    def __init__(self):
        self.API_SECRET = os.getenv("API_SECRET", "")
        # Runtime identity bypasses are not supported; tests use dependency overrides.
        self.ENFORCE_AUTH = True
        _cors_raw = os.getenv("CORS_ORIGINS", "*")
        self.CORS_ORIGINS = (
            [o.strip() for o in _cors_raw.split(",")]
            if "," in _cors_raw
            else ([_cors_raw.strip()] if _cors_raw != "*" else ["*"])
        )

        env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower().strip()
        if env in ("prod", "production"):
            self.ENFORCE_AUTH = True


def validate_security_config(cfg=None):
    """
    Production security hardening validator.
    Fails startup immediately if insecure auth, secret, or CORS settings are detected in production.
    """
    if cfg is None:
        cfg = api_cfg

    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower().strip()
    is_production = env in ("prod", "production")

    if is_production:
        # 1. ENFORCE_AUTH must always evaluate to True in production
        cfg.ENFORCE_AUTH = True

        # 2. Secret validation
        secret = (cfg.API_SECRET or "").strip()
        if not secret:
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: API_SECRET is missing or empty in production mode. "
                "Startup aborted."
            )
        if secret in KNOWN_INSECURE_SECRETS or len(secret) < 16:
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: Insecure or development default API_SECRET detected in production mode. "
                "Production secret must be at least 16 characters long and not a known default string. Startup aborted."
            )

        # 3. CORS validation
        if cfg.CORS_ORIGINS == ["*"]:
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: Wildcard CORS origin ['*'] detected in production mode. "
                "Set CORS_ORIGINS to trusted domain(s). Startup aborted."
            )


# ─────────────────────────────────────────────
# DATASET (FER2013)
# ─────────────────────────────────────────────
class DatasetConfig:
    # Download from: https://www.kaggle.com/datasets/msambare/fer2013
    FER2013_PATH = DATA_DIR / "fer2013.csv"
    TRAIN_DIR = DATA_DIR / "train"
    TEST_DIR = DATA_DIR / "test"
    VALIDATION_SPLIT = 0.2
    RANDOM_SEED = 42


# ─────────────────────────────────────────────
# MASTERY SYSTEM (Phase B1 Refinements)
# ─────────────────────────────────────────────
class MasteryConfig:
    SMOOTHING_FACTOR = float(os.getenv("MASTERY_SMOOTHING_FACTOR", "0.25"))
    DIFFICULTY_WEIGHTS = {"beginner": 0.6, "intermediate": 1.0, "advanced": 1.4}


# ─────────────────────────────────────────────
# CONVENIENCE: single import point
# ─────────────────────────────────────────────
emotion_cfg = EmotionConfig()
nlp_cfg = NLPConfig()
tutor_cfg = TutorConfig()
session_cfg = SessionConfig()
api_cfg = APIConfig()
dataset_cfg = DatasetConfig()
mastery_cfg = MasteryConfig()
