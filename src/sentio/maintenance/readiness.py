"""Capability probes without inference, model downloads or additional DB owners."""

from sentio.config import emotion_cfg, nlp_cfg


def ai_readiness():
    import requests

    model = nlp_cfg.OLLAMA_MODEL
    try:
        reply = requests.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/tags", timeout=1)
        reply.raise_for_status()
        names = {item["name"] for item in reply.json().get("models", [])}
        present = model in names or (":" not in model and model + ":latest" in names)
        return {
            "ready": present,
            "model": model,
            "action": "" if present else f"Install the configured model: ollama pull {model}",
        }
    except (requests.RequestException, ValueError, KeyError):
        return {"ready": False, "model": model, "action": "Start Ollama and retry."}


def readiness(agent):
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    storage = False
    if agent.sm.persister._engine is not None:
        try:
            with agent.sm.persister._engine.connect() as connection:
                storage = connection.execute(text("SELECT 1")).scalar() == 1
        except SQLAlchemyError:
            storage = False
    from sentio.ingestion.ocr import ExtractionError, require_ocr

    try:
        require_ocr(pdf=True)
        ocr = {"ready": True, "action": ""}
    except ExtractionError as exc:
        ocr = {"ready": False, "action": str(exc)}
    return {
        "storage": {
            "ready": storage,
            "action": ""
            if storage
            else "Check the data directory permissions and restore a verified backup if needed.",
        },
        "ai": ai_readiness(),
        "retrieval": {
            "ready": "retrieval" not in agent.startup_errors and storage,
            "vector_store_ready": agent.kb.vdb.is_available(),
            "semantic": storage
            and agent.kb.vdb.is_available()
            and agent.kb.retriever._model is not None,
        },
        "ocr": ocr,
        "camera": {
            "ready": agent.detector.model is not None,
            "experimental": True,
            "weights_available": emotion_cfg.MODEL_PATH.exists(),
            "enabled": emotion_cfg.ENABLED,
        },
    }
