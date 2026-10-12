"""Cancellable turns with durable idempotency and a single publication boundary."""

import hashlib
import json
import logging
import time
from copy import deepcopy
from queue import Full, Queue
from threading import RLock

from sqlalchemy import text

from sentio.jobs.control import WorkCancelled

logger = logging.getLogger(__name__)


def study_fingerprint(session):
    return json.dumps(
        [
            session.subject,
            session.topic,
            session.metadata.get("document_id"),
        ],
        sort_keys=True,
    )


class StreamService:
    def __init__(self, agent, jobs):
        self.agent = agent
        self.jobs = jobs
        self.engine = agent.sm.persister._engine
        self.lock = RLock()
        self.active = {}
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE chat_requests SET status='failed' WHERE status='running'"))

    def begin(self, owner, session_id, request_id, message):
        events = Queue(maxsize=256)
        session = self.agent.sm.get_or_raise(session_id)
        if session.student_id != owner:
            raise PermissionError("Session does not belong to this learner.")
        context = self.context(session)
        fingerprint = hashlib.sha256((message + context).encode()).hexdigest()
        params = {
            "owner": owner,
            "session": session_id,
            "request": request_id,
            "fingerprint": fingerprint,
            "now": time.time(),
            "message": message,
            "context": context,
        }
        with self.lock:
            with self.engine.begin() as conn:
                previous = (
                    conn.execute(
                        text(
                            "SELECT * FROM chat_requests WHERE session_id=:session AND request_id=:request AND student_id=:owner"
                        ),
                        params,
                    )
                    .mappings()
                    .first()
                )
                if previous and previous["fingerprint"] != fingerprint:
                    raise ValueError(
                        "Request ID already belongs to a different message or study context."
                    )
                if previous and previous["status"] == "complete":
                    events.put(("complete", json.loads(previous["result_json"])))
                    return events, None
                if session_id in self.active:
                    raise ValueError(
                        "A tutor turn is already running for this session. Stop it before starting another."
                    )
                conn.execute(
                    text(
                        "INSERT OR REPLACE INTO chat_requests (session_id,request_id,student_id,fingerprint,status,updated_at,message,context) VALUES (:session,:request,:owner,:fingerprint,'running',:now,:message,:context)"
                    ),
                    params,
                )
            self.active[session_id] = {"owner": owner, "request": request_id, "job_id": None}

            def emit(kind, data):
                try:
                    events.put_nowait((kind, data))
                except Full as exc:
                    raise WorkCancelled("Client could not keep up with the answer") from exc

            def work(control):
                control.emit = emit
                control.defer_turn = True
                control.progress = lambda stage: emit("status", {"stage": stage})
                try:
                    control.check()
                    self.agent.nlp.clear_history(session_id)
                    history = self.agent.nlp._get_history(session_id)
                    for turn in self.turns(owner, session_id, limit=10):
                        history.add_user(turn["message"])
                        history.add_assistant(turn["response"]["text"])
                    response = self.agent.chat(session_id, message, defer_turn=True)
                    control.check()
                    if self.context(session) != context or not session.is_active:
                        raise WorkCancelled("Study context changed")

                    def save():
                        snapshot = deepcopy(session.__dict__)
                        try:
                            session.metadata["strategy"] = response.strategy
                            session.metadata["learning_state"] = response.learning_state
                            if session.difficulty != response.difficulty:
                                session.update_difficulty(
                                    response.difficulty, "completed_tutor_turn"
                                )
                            session.record_exchange(
                                tokens=response.tutor_response.tokens_used,
                                latency_ms=response.tutor_response.latency_ms,
                            )
                            response.total_exchanges = session.total_exchanges
                            result = response.to_dict()
                            with self.engine.begin() as conn:
                                conn.exec_driver_sql("BEGIN IMMEDIATE")
                                if not conn.execute(
                                    text(
                                        "SELECT student_id FROM student_accounts WHERE student_id=:owner"
                                    ),
                                    params,
                                ).first():
                                    raise WorkCancelled("Account is no longer available")
                                if self.context(session, connection=conn) != context:
                                    raise WorkCancelled("Study sources changed before saving")
                                self.agent.sm.persister.save_session(session, connection=conn)
                                conn.execute(
                                    text(
                                        "UPDATE chat_requests SET status='complete', result_json=:result,updated_at=:now WHERE session_id=:session AND request_id=:request AND student_id=:owner"
                                    ),
                                    {**params, "result": json.dumps(result), "now": time.time()},
                                )
                            history = self.agent.nlp._get_history(session_id)
                            history.add_user(message)
                            history.add_assistant(result["text"])
                            return result
                        except Exception:
                            session.__dict__.clear()
                            session.__dict__.update(snapshot)
                            raise

                    result = control.commit(save)
                    emit("complete", result)
                    return result
                except WorkCancelled:
                    self._fail(params)
                    emit("cancelled", {"detail": "Turn stopped before saving."})
                    raise
                except Exception:
                    self._fail(params)
                    logger.exception("Tutor turn failed for %s", session_id[:8])
                    emit(
                        "error",
                        {
                            "detail": "The tutor could not finish this answer. Check AI readiness and retry."
                        },
                    )
                    raise

            try:

                def finished():
                    with self.lock:
                        self.active.pop(session_id, None)
                    if events.empty():
                        self._fail(params)
                        emit("cancelled", {"detail": "Queued turn stopped before saving."})

                job = self.jobs.submit(owner, "chat", work, on_done=finished)
                self.active[session_id]["job_id"] = job["job_id"]
            except Exception:
                self.active.pop(session_id, None)
                self._fail(params)
                raise
        return events, job["job_id"]

    def _fail(self, params):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE chat_requests SET status='failed',updated_at=:now WHERE session_id=:session AND request_id=:request AND status!='complete'"
                ),
                {**params, "now": time.time()},
            )

    def cancel(self, owner, session_id, request_id):
        with self.lock:
            active = self.active.get(session_id)
            if not active or active["owner"] != owner or active["request"] != request_id:
                return False
            return self.jobs.cancel(active["job_id"], owner)

    def cancel_session(self, owner, session_id):
        with self.lock:
            active = self.active.get(session_id)
            if active and active["owner"] == owner:
                return self.cancel(owner, session_id, active["request"])
            return False

    def turns(self, owner, session_id, limit=50, offset=0):
        context = self.context(self.agent.sm.get_or_raise(session_id))
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT request_id,message,result_json FROM chat_requests WHERE student_id=:owner AND session_id=:session AND context=:context AND status='complete' ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
                    ),
                    {
                        "owner": owner,
                        "session": session_id,
                        "context": context,
                        "limit": limit,
                        "offset": offset,
                    },
                )
                .mappings()
                .all()
            )
        return [
            {
                "request_id": row["request_id"],
                "message": row["message"],
                "response": json.loads(row["result_json"]),
            }
            for row in reversed(rows)
        ]

    def context(self, session, connection=None):
        selected = session.metadata.get("document_id")
        versions = []
        if selected not in (None, "none"):
            if connection is None:
                documents = self.agent.sm.list_documents(student_id=session.student_id)
            else:
                documents = (
                    connection.execute(
                        text("SELECT id,checksum FROM documents WHERE student_id=:owner"),
                        {"owner": session.student_id},
                    )
                    .mappings()
                    .all()
                )
            ids = selected if isinstance(selected, list) else [selected]
            versions = sorted(
                (d["id"], d["checksum"]) for d in documents if selected == "all" or d["id"] in ids
            )
        return json.dumps([study_fingerprint(session), versions], sort_keys=True)
