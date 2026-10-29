import json
import time
import uuid

from sqlalchemy import text


class JobConflict(ValueError):
    pass


class JobExpired(ValueError):
    pass


class JobRepository:
    def __init__(self, engine):
        self.engine = engine

    def recover(self):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE jobs SET status='failed', stage='interrupted', error='Application interrupted this job. Retry explicitly.', updated_at=:now WHERE status IN ('queued','running','cancelling')"
                ),
                {"now": time.time()},
            )
            conn.execute(
                text(
                    "DELETE FROM jobs WHERE status IN ('succeeded','failed','cancelled') AND updated_at < :cutoff"
                ),
                {"cutoff": time.time() - 7 * 86400},
            )

    def replay(self, owner, kind, request_id, fingerprint):
        if not request_id:
            return None
        with self.engine.connect() as connection:
            previous = connection.execute(
                text(
                    "SELECT kind,fingerprint,job_id FROM job_requests WHERE student_id=:owner AND request_id=:request"
                ),
                {"owner": owner, "request": request_id},
            ).first()
        if previous is None:
            return None
        if previous[0] != kind or previous[1] != fingerprint:
            raise JobConflict("Submission ID was reused with different content or study context.")
        record = self.get(previous[2], owner)
        if record is None:
            raise JobExpired(
                "This submission's job status has expired. Check saved work before starting a new submission."
            )
        return record

    def create(self, owner, kind, lane, request_id=None, fingerprint=None, study_context=None):
        job_id = str(uuid.uuid4())
        now = time.time()
        with self.engine.begin() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            if request_id:
                conn.execute(
                    text(
                        "INSERT INTO job_requests VALUES (:owner,:request,:kind,:fingerprint,:id,:now)"
                    ),
                    {
                        "owner": owner,
                        "request": request_id,
                        "kind": kind,
                        "fingerprint": fingerprint,
                        "id": job_id,
                        "now": now,
                    },
                )
            conn.execute(
                text(
                    "DELETE FROM jobs WHERE student_id=:owner AND status IN ('succeeded','failed','cancelled') AND job_id NOT IN (SELECT job_id FROM jobs WHERE student_id=:owner ORDER BY updated_at DESC LIMIT 500)"
                ),
                {"owner": owner},
            )
            conn.execute(
                text(
                    "INSERT INTO jobs (job_id,student_id,kind,lane,status,stage,created_at,updated_at,context_json) VALUES (:id,:owner,:kind,:lane,'queued','queued',:now,:now,:context)"
                ),
                {
                    "id": job_id,
                    "owner": owner,
                    "kind": kind,
                    "lane": lane,
                    "now": now,
                    "context": json.dumps(study_context) if study_context is not None else None,
                },
            )
        return self.get(job_id, owner)

    def get(self, job_id, owner):
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM jobs WHERE job_id=:id AND student_id=:owner"),
                    {"id": job_id, "owner": owner},
                )
                .mappings()
                .first()
            )
        if not row:
            return None
        result = dict(row)
        result["result"] = json.loads(result.pop("result_json") or "null")
        result["study_context"] = json.loads(result.pop("context_json") or "null")
        return result

    def update(self, job_id, status, stage, result=None, error=None):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE jobs SET status=:status,stage=:stage,result_json=:result,error=:error,updated_at=:now WHERE job_id=:id AND status NOT IN ('succeeded','failed','cancelled') AND (:status != 'running' OR status != 'cancelling')"
                ),
                {
                    "status": status,
                    "stage": stage,
                    "result": json.dumps(result) if result is not None else None,
                    "error": error,
                    "now": time.time(),
                    "id": job_id,
                },
            )
