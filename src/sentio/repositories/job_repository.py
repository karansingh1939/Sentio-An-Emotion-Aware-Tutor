import json
import time
import uuid

from sqlalchemy import text


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

    def create(self, owner, kind, lane):
        job_id = str(uuid.uuid4())
        now = time.time()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM jobs WHERE student_id=:owner AND status IN ('succeeded','failed','cancelled') AND job_id NOT IN (SELECT job_id FROM jobs WHERE student_id=:owner ORDER BY updated_at DESC LIMIT 500)"
                ),
                {"owner": owner},
            )
            conn.execute(
                text(
                    "INSERT INTO jobs (job_id,student_id,kind,lane,status,stage,created_at,updated_at) VALUES (:id,:owner,:kind,:lane,'queued','queued',:now,:now)"
                ),
                {"id": job_id, "owner": owner, "kind": kind, "lane": lane, "now": now},
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
