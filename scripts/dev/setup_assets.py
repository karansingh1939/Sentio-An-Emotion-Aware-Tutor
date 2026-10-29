#!/usr/bin/env python
"""
setup_assets.py — Sentio Workspace Bootstrapping and Asset Setup
================================================================
This script initializes the directory structure and verifies or downloads
required model assets (specifically models/emotion_model.h5) for runtime inference.
"""

import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Constants
BASE_DIR = Path(__file__).resolve().parents[2]
REQUIRED_DIRS = [
    BASE_DIR / "data",
    BASE_DIR / "models",
    BASE_DIR / "logs",
    BASE_DIR / "models" / "checkpoints",
]

MODEL_PATH = BASE_DIR / "models" / "emotion_model.h5"
# Public release asset URL for Sentio emotion model
MODEL_URL = "https://github.com/karansingh1939/Sentio-An-Emotion-Aware-Tutor/releases/download/v1.0.0/emotion_model.h5"


def create_directories():
    logger.info("Initializing directory structure...")
    for directory in REQUIRED_DIRS:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            logger.info("Created directory: %s", directory.relative_to(BASE_DIR))
        else:
            logger.info("Directory exists: %s", directory.relative_to(BASE_DIR))


def verify_or_download_model():
    if MODEL_PATH.exists():
        size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
        logger.info(
            "Found emotion model at %s (%.2f MB)", MODEL_PATH.relative_to(BASE_DIR), size_mb
        )
        return True

    logger.warning("Emotion model (emotion_model.h5) is missing.")
    logger.info("Attempting to download from release repository...")
    try:

        def progress_callback(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            sys.stdout.write(f"\rDownloading: {percent:.1f}%")
            sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=progress_callback)
        sys.stdout.write("\n")
        logger.info("Successfully downloaded emotion_model.h5!")
        return True
    except Exception as e:
        sys.stdout.write("\n")
        logger.error("Download failed or release asset is not yet published: %s", e)
        logger.info("Remediation Options:")
        logger.info("  Option 1: Train the model locally by running: python scripts/emotion/train.py")
        logger.info(
            "  Option 2: Manually place a pre-trained emotion_model.h5 in the models/ directory."
        )
        return False


def main():
    logger.info("Starting Sentio Workspace Setup...")
    create_directories()
    model_verified = verify_or_download_model()
    if model_verified:
        logger.info("Sentio Workspace Setup completed successfully!")
    else:
        logger.warning(
            "Sentio Workspace Setup completed with warnings. Refer to manual setup instructions."
        )


if __name__ == "__main__":
    main()
