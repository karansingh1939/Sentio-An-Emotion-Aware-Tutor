"""
utils.py -- Shared Utilities for Emotion-Aware AI Tutor
========================================================
Contains:
  - Logging setup (structured, colour-coded console + rotating file)
  - Image preprocessing helpers
  - JSON read/write helpers
  - Stopwatch / Timer class
  - System health check (GPU, deps, model files)
  - Text helpers (truncate, sanitise)
  - Rate limiter (token bucket) for webcam / API calls
"""

import json
import logging
import logging.handlers
import sys
import time
from pathlib import Path

import numpy as np

from sentio.config import LOG_DIR, emotion_cfg

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────


class ColorFormatter(logging.Formatter):
    """ANSI colour codes for console log levels."""

    COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = "%s%s%s" % (color, record.levelname, self.RESET)
        return super().format(record)


def setup_logging(
    level=logging.INFO,
    log_file=None,
    max_bytes=5 * 1024 * 1024,  # 5 MB
    backup_count=3,
):
    """
    Configure root logger with:
      - Coloured console handler
      - Optional rotating file handler

    Call once at application startup (e.g. in app.py or train script).

    Args:
        level        : Logging level (default INFO)
        log_file     : Path to log file. If None, logs/tutor.log is used.
        max_bytes    : Max log file size before rotation
        backup_count : Number of rotated log files to keep
    """
    log_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter(log_fmt, datefmt=date_fmt))
    root.addHandler(console)

    # File handler
    log_path = Path(log_file) if log_file else LOG_DIR / "tutor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt=date_fmt))
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    return root


# ─────────────────────────────────────────────
# TIMER / STOPWATCH
# ─────────────────────────────────────────────


class Timer:
    """
    Context manager and standalone stopwatch.

    Usage as context manager:
        with Timer("inference") as t:
            model.predict(x)
        print(t.elapsed_ms)

    Usage standalone:
        t = Timer()
        t.start()
        ...
        print(t.stop_ms())
    """

    def __init__(self, label=""):
        self.label = label
        self._start = None
        self.elapsed_ms = 0.0

    def start(self):
        self._start = time.perf_counter()
        return self

    def stop_ms(self):
        if self._start is None:
            return 0.0
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._start = None
        return self.elapsed_ms

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop_ms()
        if self.label:
            logger = logging.getLogger(__name__)
            logger.debug("[Timer] %s: %.1f ms", self.label, self.elapsed_ms)


# ─────────────────────────────────────────────
# IMAGE UTILITIES
# ─────────────────────────────────────────────


def bgr_to_gray(frame):
    """
    Convert BGR numpy array to grayscale.

    Args:
        frame: uint8 numpy array shape (H, W, 3) or (H, W)

    Returns:
        uint8 numpy array shape (H, W)
    """
    import cv2

    if frame.ndim == 2:
        return frame
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def resize_frame(frame, width=640, height=480):
    """
    Resize a frame to the given dimensions.

    Args:
        frame  : numpy array
        width  : target width in pixels
        height : target height in pixels

    Returns:
        Resized numpy array
    """
    import cv2

    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)


def normalise_image(img):
    """
    Normalise a uint8 image array to float32 in [0, 1].

    Args:
        img: numpy uint8 array

    Returns:
        numpy float32 array
    """
    return img.astype(np.float32) / 255.0


def pad_to_square(img):
    """
    Zero-pad an image to make it square (max(H, W) x max(H, W)).
    Useful before resizing to avoid aspect-ratio distortion.

    Args:
        img: numpy array (H, W) or (H, W, C)

    Returns:
        Square numpy array
    """
    h, w = img.shape[:2]
    if h == w:
        return img
    size = max(h, w)
    if img.ndim == 2:
        padded = np.zeros((size, size), dtype=img.dtype)
    else:
        padded = np.zeros((size, size, img.shape[2]), dtype=img.dtype)
    pad_h = (size - h) // 2
    pad_w = (size - w) // 2
    padded[pad_h : pad_h + h, pad_w : pad_w + w] = img
    return padded


def encode_frame_base64(frame):
    """
    Encode a BGR numpy frame to a base64 JPEG string for API transmission.

    Args:
        frame: uint8 BGR numpy array

    Returns:
        str -- base64-encoded JPEG
    """
    import base64

    import cv2

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf).decode("utf-8")


def decode_frame_base64(b64_str):
    """
    Decode a base64 JPEG string back to a BGR numpy array.

    Args:
        b64_str: str -- base64-encoded JPEG

    Returns:
        uint8 BGR numpy array
    """
    import base64

    import cv2

    buf = np.frombuffer(base64.b64decode(b64_str), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


# ─────────────────────────────────────────────
# JSON UTILITIES
# ─────────────────────────────────────────────


def read_json(path):
    """
    Read a JSON file and return its contents.

    Args:
        path: str or Path

    Returns:
        Parsed Python object, or None if file not found
    """
    path = Path(path)
    if not path.exists():
        logging.getLogger(__name__).warning("JSON file not found: %s", path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data, indent=2):
    """
    Serialise data to a JSON file, creating parent dirs as needed.

    Args:
        path   : str or Path
        data   : JSON-serialisable Python object
        indent : Indentation level (default 2)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, default=_json_default)


def _json_default(obj):
    """Fallback serialiser for numpy types, Paths, etc."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def safe_json_loads(text, fallback=None):
    """
    Parse JSON string safely, returning fallback on failure.

    Args:
        text    : JSON string to parse
        fallback: Value returned on parse error (default None)
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return fallback


# ─────────────────────────────────────────────
# TEXT UTILITIES
# ─────────────────────────────────────────────


def truncate(text, max_chars=200, suffix="..."):
    """
    Truncate text to max_chars, appending suffix if trimmed.

    Args:
        text      : Input string
        max_chars : Maximum character length
        suffix    : Appended when truncated

    Returns:
        Truncated string
    """
    if not text or len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def sanitise_input(text, max_length=2000):
    """
    Clean student input before sending to the LLM:
      - Strip leading/trailing whitespace
      - Remove null bytes
      - Truncate to max_length

    Args:
        text       : Raw input string
        max_length : Hard cap on input length

    Returns:
        Cleaned string
    """
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().replace("\x00", "")
    return text[:max_length]


def format_duration(seconds):
    """
    Convert seconds to human-readable string.

    Examples:
        45   -> "45s"
        130  -> "2m 10s"
        3700 -> "1h 1m 40s"
    """
    seconds = int(seconds)
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return "%dm %ds" % (m, s)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "%dh %dm %ds" % (h, m, s)


# ─────────────────────────────────────────────
# RATE LIMITER (token bucket)
# ─────────────────────────────────────────────


class RateLimiter:
    """
    Simple token-bucket rate limiter.
    Used to throttle webcam processing or API calls.

    Args:
        rate : Maximum calls per second
        burst: Maximum burst size (default = rate)

    Usage:
        limiter = RateLimiter(rate=10)    # max 10 calls/sec
        if limiter.allow():
            process_frame()
    """

    def __init__(self, rate, burst=None):
        self.rate = float(rate)
        self.burst = float(burst or rate)
        self._tokens = self.burst
        self._last = time.perf_counter()

    def allow(self):
        """
        Returns True if a call is allowed under the rate limit.
        Refills tokens based on elapsed time.
        """
        now = time.perf_counter()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_and_allow(self):
        """Block until a token is available, then consume it."""
        while not self.allow():
            time.sleep(1.0 / self.rate)

    def retry_after(self):
        import math

        return max(1, math.ceil((1 - self._tokens) / self.rate))


# ─────────────────────────────────────────────
# SYSTEM HEALTH CHECK
# ─────────────────────────────────────────────


def system_health_check():
    """
    Check system readiness and print a summary.
    Returns a dict with status flags.

    Checks:
      - Python version
      - GPU availability (TensorFlow)
      - Required packages
      - Model file existence
      - Webcam availability
    """
    import platform
    from importlib.metadata import PackageNotFoundError, version

    logger = logging.getLogger(__name__)
    report = {}

    # Python version
    py_version = platform.python_version()
    report["python_version"] = py_version
    logger.info("Python %s", py_version)

    # Installed package metadata only; camera runtime is deliberately lazy.
    try:
        report["tensorflow"] = version("tensorflow")
        report["gpu_count"] = None
    except PackageNotFoundError:
        report["tensorflow"] = None
        report["gpu_count"] = 0
        logger.warning("TensorFlow not installed.")

    # OpenCV
    try:
        import cv2

        report["opencv"] = cv2.__version__
        logger.info("OpenCV %s", cv2.__version__)
    except ImportError:
        report["opencv"] = None
        logger.warning("OpenCV not installed.")

    # Optional packages
    optional = {
        "openai": "openai",
        "sentence_transformers": "sentence-transformers",
        "sqlalchemy": "sqlalchemy",
        "sklearn": "scikit-learn",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
        "transformers": "transformers",
    }
    report["optional_packages"] = {}
    for pip_name in optional.values():
        try:
            report["optional_packages"][pip_name] = version(pip_name)
        except PackageNotFoundError:
            report["optional_packages"][pip_name] = None

    # Model file
    model_path = emotion_cfg.MODEL_PATH
    report["emotion_model_exists"] = Path(model_path).exists()
    if report["emotion_model_exists"]:
        size_mb = Path(model_path).stat().st_size / (1024 * 1024)
        logger.info("Emotion model found: %s (%.1f MB)", model_path, size_mb)
    else:
        logger.warning(
            "Emotion model NOT found at %s. Run: python train_emotion_model.py", model_path
        )

    # Webcam (Skipped physical check in backend context to avoid blocking/timeouts)
    report["webcam_available"] = False
    logger.info("Webcam available: %s (headless server context)", report["webcam_available"])

    # Never acquire a second persistent vector-store owner during health probes.
    report["qdrant_status"] = "not probed; use /api/v1/ready"

    # Ollama status
    try:
        import requests

        from sentio.config import nlp_cfg

        r = requests.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/tags", timeout=1.5)
        if r.status_code == 200:
            models_data = r.json()
            models_list = [m["name"] for m in models_data.get("models", [])]
            model_target = nlp_cfg.OLLAMA_MODEL
            model_found = False
            for m in models_list:
                if m == model_target or m.split(":")[0] == model_target.split(":")[0]:
                    model_found = True
                    break

            if model_found:
                report["ollama_status"] = f"available (model: {nlp_cfg.OLLAMA_MODEL})"
            else:
                report["ollama_status"] = (
                    f"model_missing (need: ollama pull {nlp_cfg.OLLAMA_MODEL})"
                )
        else:
            report["ollama_status"] = "unavailable"
    except Exception:
        report["ollama_status"] = "unavailable"

    return report


def print_health_report(report):
    """Pretty-print the result of system_health_check()."""
    ok = "OK"
    err = "MISSING"
    warn = "WARNING"

    print("\n" + "=" * 50)
    print("  EMOTION-AWARE TUTOR -- SYSTEM HEALTH CHECK")
    print("=" * 50)
    print("  Python          :", report.get("python_version"))
    print("  TensorFlow      :", report.get("tensorflow") or err)
    print("  OpenCV          :", report.get("opencv") or err)
    print("  GPU count       :", report.get("gpu_count", 0))
    print("  Emotion model   :", ok if report.get("emotion_model_exists") else warn)
    print("  Webcam          :", ok if report.get("webcam_available") else warn)

    # Ollama
    ollama_stat = report.get("ollama_status", "unavailable")
    if "available" in ollama_stat:
        print("  Ollama Status   :", ok, f"({ollama_stat})")
    elif "model_missing" in ollama_stat:
        print("  Ollama Status   :", warn, f"({ollama_stat})")
    else:
        print("  Ollama Status   :", warn, "(Ollama server is offline or unreachable)")

    # Qdrant
    qdrant_stat = report.get("qdrant_status", "unavailable")
    if qdrant_stat in ("external", "in-memory"):
        print("  Qdrant Status   :", ok, f"({qdrant_stat} mode)")
    else:
        print("  Qdrant Status   :", warn, "(Qdrant client not installed or unavailable)")

    print("\n  Optional packages:")
    for pkg, ver in report.get("optional_packages", {}).items():
        status = ver if ver else err
        print("    %-28s: %s" % (pkg, status))
    print("=" * 50 + "\n")


# ─────────────────────────────────────────────
# QUICK SMOKE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    setup_logging(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    # Timer test
    with Timer("sleep_test") as t:
        time.sleep(0.05)
    print("Timer elapsed: %.1f ms" % t.elapsed_ms)

    # Text utils
    long_text = "This is a very long student message. " * 20
    print("Truncated:", truncate(long_text, max_chars=60))
    print("Duration:", format_duration(3725))

    # Rate limiter
    limiter = RateLimiter(rate=5)
    allowed = sum(1 for _ in range(10) if limiter.allow())
    print("Rate limiter allowed %d/10 calls in burst." % allowed)

    # JSON round-trip
    sample = {"emotion": "happy", "confidence": 0.92, "scores": [0.1, 0.8, 0.1]}
    write_json("/tmp/test_utils.json", sample)
    loaded = read_json("/tmp/test_utils.json")
    assert loaded == sample, "JSON round-trip failed"
    print("JSON round-trip: OK")

    # System health check
    report = system_health_check()
    print_health_report(report)
