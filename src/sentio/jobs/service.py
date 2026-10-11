import logging
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

from sentio.jobs.control import WorkCancelled, WorkControl, execution
from sentio.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, engine, queue_limit=8):
        self.repository = JobRepository(engine)
        self.repository.recover()
        self.queue_limit = queue_limit
        self.lock = RLock()
        self.controls = {}
        self.executors = {
            lane: ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"sentio-{lane}")
            for lane in ("ai", "ingestion")
        }
        self.closed = False
        self.revoked_owners = set()

    def submit(self, owner, kind, work, lane="ai", on_done=None, request_id=None, fingerprint=None):
        with self.lock:
            if self.closed or lane not in self.executors or owner in self.revoked_owners:
                raise ValueError("Job service is unavailable")
            previous = self.repository.replay(owner, kind, request_id, fingerprint)
            if previous:
                if on_done:
                    on_done()
                return previous
            if len(self.controls) >= self.queue_limit:
                raise ValueError("Local work queue is full. Wait for a job to finish.")
            record = self.repository.create(owner, kind, lane, request_id, fingerprint)
            job_id = record["job_id"]
            control = WorkControl(
                progress=lambda stage: self.repository.update(job_id, "running", stage)
            )
            self.controls[job_id] = control
            self.executors[lane].submit(self._run, job_id, control, work, on_done)
            return record

    def _run(self, job_id, control, work, on_done):
        try:
            control.check()
            self.repository.update(job_id, "running", "starting")
            with execution(control):
                result = work(control)
            if not control.committed:
                control.check()
            self.repository.update(job_id, "succeeded", "complete", result=result)
        except WorkCancelled:
            self.repository.update(job_id, "cancelled", "cancelled")
        except Exception:
            if control.cancelled.is_set():
                self.repository.update(job_id, "cancelled", "cancelled")
                return
            logger.exception("Local job %s failed", job_id)
            self.repository.update(
                job_id,
                "failed",
                "failed",
                error="Work failed. Your existing artifacts are preserved; retry or check local diagnostics.",
            )
        finally:
            if on_done:
                try:
                    on_done()
                except Exception:
                    logger.exception("Job completion cleanup failed")
            with self.lock:
                self.controls.pop(job_id, None)

    def get(self, job_id, owner):
        return self.repository.get(job_id, owner)

    def cancel(self, job_id, owner):
        with self.lock:
            record = self.get(job_id, owner)
            control = self.controls.get(job_id)
            if not record or control is None:
                return False
            if not control.cancel():
                return False
            self.repository.update(job_id, "cancelling", "cancelling")
            return True

    def close(self):
        with self.lock:
            self.closed = True
            for control in self.controls.values():
                control.cancel()
        for executor in self.executors.values():
            executor.shutdown(wait=True)

    def cancel_owner(self, owner):
        with self.lock:
            self.revoked_owners.add(owner)
            for job_id in list(self.controls):
                if self.get(job_id, owner):
                    self.cancel(job_id, owner)
