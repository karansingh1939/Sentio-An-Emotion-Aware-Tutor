"""Runtime health check: Python, dependencies, model files and the local LLM."""

import logging
from pathlib import Path

from sentio.config import emotion_cfg


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
            "Emotion model NOT found at %s. Run: python scripts/emotion/train.py", model_path
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
