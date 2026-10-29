#!/usr/bin/env python
"""
check_environment.py — Sentio Environment Verification Utility
==============================================================
Validates Python runtime, dependencies, system variables, and service connections.
"""

import logging
import re
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# Add project root to path to allow importing sentio
BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_python_version():
    logger.info("Checking Python version...")
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) == (3, 12):
        logger.info("  [OK] Python %d.%d.%d", major, minor, sys.version_info.micro)
        return True
    else:
        logger.error("  [FAIL] Python 3.12 required. Found %d.%d", major, minor)
        return False


def check_dependencies():
    logger.info("Checking required package installations...")
    with (BASE_DIR / "pyproject.toml").open("rb") as manifest:
        dependencies = tomllib.load(manifest)["project"]["dependencies"]
    missing = []
    for requirement in dependencies:
        package = re.match(r"[A-Za-z0-9_.-]+", requirement).group()
        try:
            version(package)
        except PackageNotFoundError:
            missing.append(package)
    if missing:
        logger.error("  [FAIL] Missing packages: %s", ", ".join(missing))
        logger.info("  Run uv sync, then uv run python scripts/dev/check_environment.py")
        return False
    logger.info("  [OK] All required packages are installed. Use uv sync to enforce versions.")
    return True


def check_environment_variables():
    logger.info("Checking environment variables...")
    from sentio.config import nlp_cfg

    logger.info("  Ollama: %s (model %s)", nlp_cfg.OLLAMA_BASE_URL, nlp_cfg.OLLAMA_MODEL)
    return True


def check_local_model():
    logger.info("Checking emotion model availability...")
    model_path = BASE_DIR / "models" / "emotion_model.h5"
    if model_path.exists():
        logger.info("  [OK] Found emotion model weights at models/emotion_model.h5")
        return True
    else:
        logger.error("  [FAIL] Missing models/emotion_model.h5")
        logger.info("  Please run: python scripts/dev/setup_assets.py")
        return False


def check_database_initialization():
    logger.info("Checking SQLite database initialization...")
    try:
        from sqlalchemy import text

        from sentio.repositories.sessions import SessionPersister

        persister = SessionPersister()
        # Initialize engine if not already done
        persister.load()  # triggers connection engine setup and table creation
        with persister._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("  [OK] SQLite session database connection successful.")
        return True
    except Exception as e:
        logger.error("  [FAIL] SQLite database initialization failed: %s", e)
        return False


def check_qdrant_availability():
    logger.info("Checking Qdrant vector store availability...")
    try:
        from sentio.rag.vector_db import QdrantVectorDB

        client = QdrantVectorDB()
        if not client.connect():
            logger.warning("  [WARN] Qdrant unavailable; keyword search will be used.")
            return True
        client.client.close()
        logger.info("  [OK] Qdrant local client connected successfully.")
        return True
    except Exception as e:
        logger.warning("  [WARN] Qdrant connection failed: %s", e)
        logger.info(
            "  (Note: System will use RAG keyword-search fallback if Qdrant is unavailable)"
        )
        return True


def main():
    logger.info("==================================================")
    logger.info("         SENTIO ENVIRONMENT HEALTH CHECK          ")
    logger.info("==================================================")

    success = True
    success &= check_python_version()
    success &= check_dependencies()
    success &= check_environment_variables()
    success &= check_local_model()
    success &= check_database_initialization()
    success &= check_qdrant_availability()

    logger.info("==================================================")
    if success:
        logger.info("STATUS: Ready! The Sentio environment is fully configured.")
        sys.exit(0)
    else:
        logger.error("STATUS: Actions required. Resolve the failures before launching.")
        sys.exit(1)


if __name__ == "__main__":
    main()
