"""Run the live regression set against a running Sentio with the owner's lecture notes.

Usage:
  python scripts/eval/live_regression.py --home "C:/ai project/tmp/manual-test-home" \
      --student stu_e157cdc7b546 [--base http://localhost:8001] [--only id1,id2]

Signs a short-lived access token for the given local account with the app's own local
signing key (development homes only), starts one session per case, sends the turns,
and checks the last answer against tests/fixtures/live_regression/cases.json. Prints
one line per case and a pass count; exits non-zero if any case fails.

Modes: "generated" = an explained answer from the notes; "refused" = the notes don't
cover it; "unverified" = the tutor said it couldn't check an answer and showed slides.
"""

import argparse
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import jwt
import requests

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "live_regression" / "cases.json"
REFUSALS = ("don't cover", "Neither this lecture")


def token(home, student):
    db = Path(home) / "data" / "tutor_sessions.db"
    with sqlite3.connect(db) as connection:
        email, role, version = connection.execute(
            "SELECT email, role, token_version FROM student_accounts WHERE student_id=?",
            (student,),
        ).fetchone()
    secret = (db.parent / ".sentio-secret").read_text().strip().encode()
    now = time.time()
    payload = {
        "sub": student,
        "email": email,
        "role": role,
        "token_type": "access",
        "version": version,
        "iss": "sentio",
        "exp": now + 3600,
        "iat": int(now),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def ask(base, headers, session_id, message):
    for _ in range(30):
        response = requests.post(
            f"{base}/sessions/{session_id}/chat/stream",
            json={"message": message, "request_id": "live-" + uuid.uuid4().hex},
            headers=headers,
            stream=True,
            timeout=900,
        )
        if response.status_code not in (409, 429):
            break
        time.sleep(10)  # the local model is busy with another request
    event, result = None, {}
    for line in response.iter_lines(decode_unicode=True):
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: ") and event == "complete":
            result = json.loads(line[6:])
    return result


def mode(result):
    text, used = result.get("text") or "", result.get("answer_mode") or ""
    if any(phrase in text for phrase in REFUSALS):
        return "refused"
    if used == "source_excerpt":
        return "unverified"
    return "generated" if used else "error"


def check(case, result):
    text = result.get("text") or ""
    problems = []
    if case.get("modes") and mode(result) not in case["modes"]:
        problems.append(f"mode {mode(result)} not in {case['modes']}")
    if case.get("any") and not any(word in text for word in case["any"]):
        problems.append(f"none of {case['any']}")
    problems += [f"missing {word!r}" for word in case.get("all", []) if word not in text]
    problems += [f"contains {word!r}" for word in case.get("none", []) if word in text]
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--student", required=True)
    parser.add_argument("--base", default="http://localhost:8001")
    parser.add_argument("--only", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    base = args.base.rstrip("/") + "/api/v1"
    spec = json.loads(CASES.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {token(args.home, args.student)}"}
    documents = requests.get(f"{base}/documents", headers=headers, timeout=60).json()["documents"]
    courses = requests.get(f"{base}/courses", headers=headers, timeout=60).json()["courses"]
    by_name = {d["filename"]: d["id"] for d in documents}
    sources = {key: by_name[name] for key, name in spec["documents"].items()}
    course = next((f"course:{c['id']}" for c in courses), None)
    only = set(filter(None, args.only.split(",")))
    rows, passed = [], 0
    for case in spec["cases"]:
        if only and case["id"] not in only:
            continue
        source = course if case["source"] == "course" else sources[case["source"]]
        session = requests.post(
            f"{base}/sessions",
            headers=headers,
            timeout=60,
            json={
                "student_id": args.student,
                "subject": "Live regression",
                "topic": "Any topic",
                "difficulty": "beginner",
                "metadata": {"document_id": source},
            },
        ).json()
        started = time.time()
        for turn in case["turns"]:
            result = ask(base, headers, session["session_id"], turn)
        problems = check(case, result)
        passed += not problems
        row = {
            "id": case["id"],
            "ok": not problems,
            "mode": mode(result),
            "problems": problems,
            "seconds": round(time.time() - started),
            "text": (result.get("text") or "")[:400],
            "session_id": session["session_id"],
        }
        rows.append(row)
        status = "PASS" if not problems else "FAIL"
        print(
            f"{status} {case['id']:<24} {row['mode']:<10} {row['seconds']:>4}s  {'; '.join(problems)}",
            flush=True,
        )
    print(f"\n{passed}/{len(rows)} passed")
    if args.report:
        Path(args.report).write_text(
            json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8"
        )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
