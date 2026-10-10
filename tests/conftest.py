"""Keep regression runs independent of personal data and external model servers."""

import os

os.environ["QDRANT_MODE"] = "memory"

import pytest


@pytest.fixture(scope="module", autouse=True)
def isolated_runtime(tmp_path_factory):
    from types import SimpleNamespace

    import numpy as np

    from sentio import config
    from sentio.ai.providers import OllamaBackend
    from sentio.api.app import agent
    from sentio.ingestion.pipeline import DocumentIngestionPipeline
    from sentio.rag.knowledge_base import SemanticRetriever
    from tests.helpers import complete

    home = tmp_path_factory.mktemp("sentio")
    (home / "data").mkdir()
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(home)
        patch.setattr(
            config.session_cfg, "DB_URL", "sqlite:///" + (home / "data/test.db").as_posix()
        )
        patch.setattr(config.session_cfg, "SESSION_LOG_PATH", home / "sessions")
        patch.setattr(config.session_cfg, "EMOTION_LOG_PATH", home / "emotions")
        patch.setattr(config.nlp_cfg, "QDRANT_MODE", "memory")
        patch.setattr(config.tutor_cfg, "ENABLE_ADAPTIVE_TUTORING", False)
        patch.setattr("sentio.ingestion.pipeline.DATA_DIR", home / "data")
        patch.setattr("sentio.api.routes.documents.BASE_DIR", home)
        patch.setattr("sentio.api.routes.privacy.BASE_DIR", home)
        patch.setattr(OllamaBackend, "load", lambda self: None)
        patch.setattr(
            OllamaBackend, "complete", lambda self, *args, **kwargs: complete(*args, **kwargs)
        )
        patch.setattr(SemanticRetriever, "_load_model", lambda self: None)
        patch.setattr(
            DocumentIngestionPipeline,
            "_lazy_load_embedding_model",
            lambda self: setattr(
                self,
                "_embedding_model",
                self._embedding_model
                or SimpleNamespace(encode=lambda texts, **kw: np.ones((len(texts), 384))),
            ),
        )
        agent.__init__()
        yield
        if agent.sm.persister._engine is not None:
            agent.sm.persister._engine.dispose()
        if agent.kb.vdb.client is not None:
            agent.kb.vdb.client.close()


@pytest.fixture(autouse=True)
def fresh_rate_limiters():
    from sentio.api.app import app
    from sentio.api.middleware import RateLimitMiddleware

    middleware = app.middleware_stack
    while middleware is not None:
        if isinstance(middleware, RateLimitMiddleware):
            middleware.limiters.clear()
        middleware = getattr(middleware, "app", None)
