"""One sentence-embedding model per process, shared by search and uploads.

Loading all-MiniLM-L6-v2 takes seconds (and tens of seconds the first time torch is
imported), so uploads and questions reuse the same loaded model instead of each
loading its own copy.
"""

import threading

_models = {}
_lock = threading.Lock()


def embedding_model(name):
    """The loaded SentenceTransformer for `name`, loading it once on first use.

    Raises ImportError when sentence-transformers is missing, or the library's own
    error when the model files are not on this computer (it never downloads).
    """
    with _lock:
        model = _models.get(name)
        if model is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(name, device="cpu", local_files_only=True)
            _models[name] = model
        return model
