"""Exercise the installed local model through real HTTP in an isolated, disposable home."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests


def run(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Choose a new report path; existing reports are immutable")
    root = Path(__file__).resolve().parents[1]
    scratch = root / "tmp"
    scratch.mkdir(exist_ok=True)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "phi3:mini",
        "steps": [],
        "limitations": [
            "One authored physics journey, not a learning study or a model accuracy estimate.",
            "Quiz submission copies the generated reference answer to test persistence only.",
            "Qdrant uses memory mode; restart must recover evidence from persisted chunks.",
        ],
    }

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = output.with_suffix(".pending")
        pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        pending.replace(output)

    with tempfile.TemporaryDirectory(prefix="live-journey-", dir=scratch) as temporary:
        home = Path(temporary).resolve()
        if not home.is_relative_to(scratch.resolve()):
            raise ValueError("Isolated home must remain inside the workspace scratch directory")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ)
        env.update(
            {
                "SENTIO_HOME": str(home),
                "DATABASE_URL": "sqlite:///" + (home / "data/tutor_sessions.db").as_posix(),
                "ENV": "development",
                "ENVIRONMENT": "development",
                "API_SECRET": "",
                "LLM_BACKEND": "ollama",
                "OLLAMA_MODEL": "phi3:mini",
                "QDRANT_MODE": "memory",
                "PYTHONPATH": str(root / "src"),
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
        )
        process = None
        base = f"http://127.0.0.1:{port}/api/v1"
        client = requests.Session()

        def stop():
            nonlocal process
            if process is not None:
                try:
                    descendants = psutil.Process(process.pid).children(recursive=True)
                except psutil.NoSuchProcess:
                    descendants = []
                for child in reversed(descendants):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)
                _, alive = psutil.wait_procs(descendants, timeout=10)
                for child in alive:
                    child.kill()
                psutil.wait_procs(alive, timeout=10)
                process = None

        def start(log):
            nonlocal process
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "sentio.api.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=home,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Isolated application failed to start")
                try:
                    if client.get(base + "/ready", timeout=2).status_code == 200:
                        return
                except requests.RequestException:
                    pass
                time.sleep(0.25)
            raise TimeoutError("Isolated application startup timed out")

        def call(method, path, **kwargs):
            response = client.request(method, base + path, timeout=220, **kwargs)
            response.raise_for_status()
            return response.json()

        def step(name, work, required=True):
            started = time.monotonic()
            try:
                result = work()
            except Exception as exc:
                report["steps"].append(
                    {
                        "name": name,
                        "status": "failed",
                        "failure": type(exc).__name__,
                        "seconds": time.monotonic() - started,
                    }
                )
                save()
                print(name + ": failed (" + type(exc).__name__ + ")", flush=True)
                if required:
                    raise
                return None
            report["steps"].append(
                {"name": name, "status": "passed", "seconds": time.monotonic() - started}
            )
            print(name + ": passed", flush=True)
            save()
            return result

        def job(path, body):
            submitted = call("POST", path, json=body, headers={"Idempotency-Key": uuid.uuid4().hex})
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                current = call("GET", "/jobs/" + submitted["job_id"])
                if current["status"] == "succeeded":
                    return current["result"]
                if current["status"] in {"failed", "cancelled"}:
                    raise RuntimeError("Local generation job did not succeed")
                time.sleep(0.5)
            raise TimeoutError("Local generation job timed out")

        def chat(sid, question, insufficient=False):
            response = client.post(
                base + f"/sessions/{sid}/chat/stream",
                timeout=220,
                json={"message": question, "request_id": uuid.uuid4().hex},
            )
            response.raise_for_status()
            if "event: complete" not in response.text or "event: error" in response.text:
                report.setdefault("stream_failures", []).append(
                    {"question": question, "events": response.text}
                )
                raise ValueError("Stream did not complete successfully")
            if insufficient:
                if "do not provide retrievable evidence" not in response.text:
                    raise ValueError("Unsupported question was not rejected")
            elif "mechanics.txt Page" not in response.text:
                raise ValueError("Completed answer did not cite the selected notes")

        try:
            with (home / "server-private.log").open("w", encoding="utf-8") as log:
                step("startup", lambda: start(log))
                credentials = {
                    "email": f"journey-{uuid.uuid4().hex}@example.com",
                    "password": uuid.uuid4().hex + "Aa1!",
                }
                call("POST", "/auth/register", json=credentials)
                login = call("POST", "/auth/login", json=credentials)
                owner = login["student_id"]
                client.headers["Authorization"] = "Bearer " + login["access_token"]
                note = b"Newton's first law: an object remains at rest or moves at constant velocity unless acted on by a nonzero net external force. Inertia is resistance to a change in velocity. Mass measures inertia. Net force causes acceleration. A balanced net force of zero does not change velocity."
                uploaded = step(
                    "upload",
                    lambda: call(
                        "POST",
                        "/documents/upload",
                        files={"file": ("mechanics.txt", note, "text/plain")},
                        data={"subject": "physics"},
                    ),
                )
                session = call(
                    "POST",
                    "/sessions",
                    json={
                        "student_id": owner,
                        "subject": "physics",
                        "topic": "Newton's first law",
                        "difficulty": "beginner",
                        "metadata": {"document_id": uploaded["document_id"]},
                    },
                )
                sid = session["session_id"]
                step(
                    "cited_explanation",
                    lambda: chat(sid, "Explain Newton's first law and inertia using these notes."),
                    required=False,
                )
                step(
                    "unsupported_question",
                    lambda: chat(sid, "What is the boiling point of ethanol?", True),
                    required=False,
                )
                quiz = step(
                    "quiz_generation",
                    lambda: job(
                        "/quizzes/jobs",
                        {
                            "student_id": owner,
                            "session_id": sid,
                            "subject": "physics",
                            "topic": "Newton's first law",
                            "difficulty": "beginner",
                            "num_questions": 1,
                        },
                    ),
                    required=False,
                )
                if quiz:
                    step(
                        "quiz_submission",
                        lambda: call(
                            "POST",
                            f"/quizzes/{quiz['quiz_id']}/submit",
                            json={
                                "session_id": sid,
                                "answers": {
                                    str(i): q["correct_answer"]
                                    for i, q in enumerate(quiz["questions"])
                                },
                            },
                        ),
                    )
                deck = call(
                    "POST",
                    "/flashcards/decks",
                    json={"student_id": owner, "deck_name": "Mechanics"},
                )
                step(
                    "card_generation",
                    lambda: job(
                        "/flashcards/jobs",
                        {
                            "student_id": owner,
                            "session_id": sid,
                            "deck_id": deck["deck_id"],
                            "topic_id": "Newton's first law",
                            "num_cards": 1,
                        },
                    ),
                    required=False,
                )
                due = call("GET", f"/flashcards/reviews/due?student_id={owner}")
                if due["cards"]:
                    card = due["cards"][0]
                    step(
                        "card_review",
                        lambda: call(
                            "POST",
                            f"/flashcards/{card['card_id']}/review",
                            json={"quality_score": 4, "request_id": uuid.uuid4().hex},
                        ),
                    )
                step(
                    "preferences",
                    lambda: call("PUT", "/study/preferences", json={"daily_minutes": 45}),
                )
                plan = call("GET", "/study/daily-plan")
                task = plan["tasks"][0]
                step(
                    "plan_completion",
                    lambda: call(
                        "PATCH",
                        f"/study/daily-plan/{plan['day']}/tasks/{task['task_id']}",
                        json={"completed": True},
                    ),
                )
                stop()
                step("restart", lambda: start(log))

                def verify_restart():
                    if call("GET", "/study/preferences")["daily_minutes"] != 45:
                        raise ValueError("Preferences did not persist")
                    saved_plan = call("GET", "/study/daily-plan")
                    if not any(
                        t["task_id"] == task["task_id"] and t["completed_at"] is not None
                        for t in saved_plan["tasks"]
                    ):
                        raise ValueError("Task completion did not persist")
                    if (
                        quiz
                        and call("GET", "/quizzes/" + quiz["quiz_id"])["quiz_id"] != quiz["quiz_id"]
                    ):
                        raise ValueError("Quiz did not persist")
                    if not call("GET", f"/flashcards/decks?student_id={owner}")["decks"]:
                        raise ValueError("Deck did not persist")
                    if not call("GET", f"/sessions/{sid}/turns")["turns"]:
                        raise ValueError("Conversation did not persist")

                step("saved_work_and_token_after_restart", verify_restart)
                report["status"] = (
                    "failed" if any(s["status"] == "failed" for s in report["steps"]) else "passed"
                )
        except Exception as exc:
            report["status"] = "failed"
            report["failure"] = type(exc).__name__
            print("Journey failed: " + type(exc).__name__, flush=True)
        finally:
            stop()
            client.close()
            save()
            if report.get("status") == "failed":
                private_log = home / "server-private.log"
                if private_log.exists():
                    (scratch / (output.stem + "-private.log")).write_bytes(private_log.read_bytes())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    raise SystemExit(0 if result["status"] == "passed" else 1)
