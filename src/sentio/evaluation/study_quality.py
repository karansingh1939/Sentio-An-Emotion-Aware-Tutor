"""Real HTTP study observations; lexical diagnostics are never semantic ground truth."""

import hashlib
import json
import re
import time
import uuid
from pathlib import Path


def observe_answer(case, response):
    text = response.get("text", "")
    normalized = " ".join(text.lower().split())
    mode = response.get("answer_mode", "unknown")
    forbidden = [term for term in case["forbidden_terms"] if term.lower() in normalized]
    first_sentence = re.split(r"[.!?](?:\s|$)", normalized, maxsplit=1)[0]
    abstains = any(
        phrase in first_sentence
        for phrase in (
            "do not contain",
            "do not provide",
            "not enough information",
            "insufficient",
            "cannot determine",
            "not provided",
            "not specified",
        )
    )
    clarifies = any(
        phrase in normalized for phrase in ("could you clarify", "which sample", "which result")
    )
    if mode == "source_excerpt":
        outcome = "source_recovery"
    elif mode == "evidence_gate" or abstains:
        outcome = "abstention"
    elif case["kind"] == "ambiguous" and clarifies:
        outcome = "clarification"
    else:
        outcome = "generated"
    expected = {
        "answerable": outcome == "generated"
        and bool(response.get("source_citations"))
        and all(term.lower() in normalized for term in case["required_terms"]),
        "absent": outcome == "abstention",
        "ambiguous": outcome in {"abstention", "clarification"},
    }[case["kind"]]
    return {
        "outcome": outcome,
        "lexical_rubric_pass": bool(expected and not forbidden),
        "forbidden_terms_found": forbidden,
        "human_support_review": None,
    }


def evaluate_cases(dataset_path, call, client, base, owner):
    source = Path(dataset_path).read_bytes()
    dataset = json.loads(source)
    documents = dataset["documents"]
    rows = []
    for case in dataset["cases"]:
        if case["kind"] not in {"answerable", "absent", "ambiguous"}:
            raise ValueError("Unknown grounding case kind")
        note = documents[case["document"]]
        uploaded = call(
            "POST",
            "/documents/upload",
            files={"file": (case["document"], note.encode(), "text/plain")},
        )
        session = call(
            "POST",
            "/sessions",
            json={
                "student_id": owner,
                "subject": case.get("subject", "physics"),
                "topic": case["topic"],
                "metadata": {"document_id": uploaded["document_id"]},
            },
        )
        started = time.monotonic()
        row = {
            "case_id": case["id"],
            "kind": case["kind"],
            "question": case["question"],
            "document": case["document"],
        }
        try:
            stream = client.post(
                base + f"/sessions/{session['session_id']}/chat/stream",
                json={"message": case["question"], "request_id": uuid.uuid4().hex},
                timeout=220,
            )
            stream.raise_for_status()
            result = None
            for event in stream.text.split("\n\n"):
                if event.startswith("event: complete"):
                    result = json.loads(
                        next(line[6:] for line in event.splitlines() if line.startswith("data: "))
                    )
            if result is None or "event: error" in stream.text:
                raise ValueError("Study turn did not complete")
            row.update(observe_answer(case, result))
            row["response"] = {
                key: result.get(key)
                for key in ("text", "follow_up", "answer_mode", "source_citations")
            }
        except Exception as exc:
            row.update(
                outcome="error",
                error=type(exc).__name__,
                lexical_rubric_pass=False,
                human_support_review=None,
            )
        row["end_to_end_seconds"] = time.monotonic() - started
        rows.append(row)
        print(f"{case['id']}: {row['outcome']}, lexical={row['lexical_rubric_pass']}", flush=True)
    return {
        "dataset_sha256": hashlib.sha256(source).hexdigest(),
        "provenance": dataset["provenance"],
        "cases": rows,
        "summary": {
            "total": len(rows),
            "lexical_rubrics_passed": sum(row["lexical_rubric_pass"] for row in rows),
            "outcomes": {
                kind: sum(row["outcome"] == kind for row in rows)
                for kind in ("generated", "abstention", "clarification", "source_recovery", "error")
            },
            "semantic_accuracy": None,
            "independent_review": False,
        },
    }
