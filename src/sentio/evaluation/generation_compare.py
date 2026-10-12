"""Repeated CPU/schema-stream comparisons using installed models and authored fixtures."""

import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests

from sentio.ai.grounding import GROUNDING_RULES
from sentio.ai.streaming import TutorPayload, visible_text
from sentio.config import nlp_cfg
from sentio.evaluation.evidence_dataset import digest
from sentio.evaluation.latency import messages_for, quality_check


def measure(client, model, case, messages, phase, repetition):
    started = time.perf_counter()
    first_visible, final, raw = None, None, ""
    options = {"num_gpu": 0, "num_ctx": 2048, "num_predict": 256, "temperature": 0, "seed": 42}
    with client.post(
        f"{nlp_cfg.OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": True,
            "format": TutorPayload.model_json_schema(),
            "keep_alive": "5m",
            "options": options,
        },
        stream=True,
        timeout=180,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1):
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise ValueError("Inference error")
            raw += chunk.get("message", {}).get("content", "")
            if len(raw) > 200000 or time.perf_counter() - started > 180:
                raise ValueError("Evaluation response exceeded its bound")
            if first_visible is None and visible_text(raw):
                first_visible = time.perf_counter() - started
            if chunk.get("done"):
                final = chunk
    text, valid = "", False
    try:
        if final is None or final.get("done_reason") == "length":
            raise ValueError("Incomplete response")
        text = TutorPayload.model_validate_json(raw).text
        valid = True
    except ValueError:
        pass
    if case["kind"] == "absent":
        normalized = text.lower()
        lexical = (
            valid
            and any(word in normalized for word in ("notes", "source", "context", "information"))
            and any(
                word in normalized for word in ("not", "lack", "insufficient", "cannot", "missing")
            )
        )
    else:
        lexical = valid and quality_check(raw, case)
    return {
        "case_id": case["id"],
        "kind": case["kind"],
        "phase": phase,
        "repetition": repetition,
        "first_visible_seconds": first_visible,
        "completion_seconds": time.perf_counter() - started,
        "schema_valid": valid,
        "lexical_rubric_pass": bool(lexical),
        "output": raw,
        "done_reason": final.get("done_reason") if final else None,
        "prompt_tokens": final.get("prompt_eval_count") if final else None,
        "output_tokens": final.get("eval_count") if final else None,
        "load_seconds": final.get("load_duration", 0) / 1e9 if final else None,
        "messages_hash": digest(messages),
    }


def comparison_messages(case, source, profile, policy="grounding"):
    if policy not in {"legacy", "grounding"}:
        raise ValueError("Unknown prompt policy")
    messages = messages_for(case, source, profile)
    if policy == "legacy":
        for message in messages:
            if message["role"] == "system":
                message["content"] = message["content"].replace(GROUNDING_RULES + "\n", "")
    return messages


def compare_models(dataset_dir, models, output, repetitions=3, prompt_policy="grounding"):
    if repetitions < 3 or len(models) < 2 or len(set(models)) != len(models):
        raise ValueError("Use distinct installed models and at least three repetitions")
    dataset_dir, output = Path(dataset_dir).resolve(), Path(output)
    if output.exists():
        raise ValueError("Reports are immutable; choose a new output path")
    dataset = json.loads((dataset_dir / "dataset.json").read_text(encoding="utf-8"))
    sources = {}
    for name in dataset["documents"]:
        path = (dataset_dir / name).resolve()
        if not path.is_relative_to(dataset_dir):
            raise ValueError("Source must remain in the evaluation directory")
        sources[name] = path.read_text(encoding="utf-8")
    direct = next(row for row in dataset["queries"] if row["kind"] == "answerable")
    paraphrase = next(row for row in dataset["queries"] if row["kind"] == "paraphrase")
    cases = [
        direct,
        paraphrase,
        dict(
            direct, id="stream-absent", kind="absent", query="What is the boiling point of ethanol?"
        ),
    ]
    profile = {"compact": False, "history_turns": 0, "max_tokens": 256}
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": digest({"dataset": dataset, "sources": sources, "cases": cases}),
        "cases": cases,
        "hardware": {
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "logical_cpus": psutil.cpu_count(),
            "ram_bytes": psutil.virtual_memory().total,
        },
        "configuration": {
            "num_gpu": 0,
            "num_ctx": 2048,
            "num_predict": 256,
            "temperature": 0,
            "seed": 42,
            "repetitions": repetitions,
            "prompt_policy": prompt_policy,
        },
        "limitations": [
            "Three synthetic cases; lexical checks do not prove factual or teaching quality.",
            "Cold means Ollama reload; OS file caches are not cleared.",
            "Provider timings exclude FastAPI, retrieval and browser rendering.",
            "First visible means the first safe character in the text field.",
            "Ollama reported allocation is not peak process RAM; sequential model blocks can have order/thermal effects.",
        ],
        "selection": "phi3:mini remains the product baseline pending broader grounded evaluation.",
        "models": {},
    }

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = output.with_suffix(output.suffix + ".pending")
        pending.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        pending.replace(output)

    with requests.Session() as client:
        tags = client.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/tags", timeout=5)
        tags.raise_for_status()
        installed = {row["name"]: row for row in tags.json()["models"]}
        if any(model not in installed for model in models):
            raise ValueError("Models must already be installed; no downloads are permitted")
        result["ollama_version"] = client.get(
            f"{nlp_cfg.OLLAMA_BASE_URL}/api/version", timeout=5
        ).json()

        def unload(model):
            client.post(
                f"{nlp_cfg.OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "keep_alive": 0},
                timeout=180,
            ).raise_for_status()

        for model in models:
            rows = []
            result["models"][model] = {
                "digest": installed[model]["digest"],
                "weight_bytes": installed[model]["size"],
                "runs": rows,
            }
            for other in models:
                unload(other)
            try:
                for phase in ("cold", "warm"):
                    for repetition in range(1, repetitions + 1):
                        for case in cases:
                            if phase == "cold":
                                unload(model)
                            try:
                                row = measure(
                                    client,
                                    model,
                                    case,
                                    comparison_messages(
                                        case,
                                        sources[case["expected_document"]],
                                        profile,
                                        prompt_policy,
                                    ),
                                    phase,
                                    repetition,
                                )
                                row["status"] = "measured"
                            except (requests.RequestException, ValueError, KeyError) as exc:
                                row = {
                                    "case_id": case["id"],
                                    "phase": phase,
                                    "repetition": repetition,
                                    "status": "failed",
                                    "failure": type(exc).__name__,
                                }
                            rows.append(row)
                            save()
                            print(
                                f"{model} {phase} {case['id']} run {repetition}: {row['status']}, valid={row.get('schema_valid', False)}",
                                flush=True,
                            )
                loaded = client.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/ps", timeout=5).json()
                result["models"][model]["reported_allocation"] = next(
                    (
                        {"size_bytes": row.get("size"), "vram_bytes": row.get("size_vram")}
                        for row in loaded.get("models", [])
                        if row.get("name") == model
                    ),
                    None,
                )
                for phase in ("cold", "warm"):
                    samples = [
                        row for row in rows if row["phase"] == phase and row["status"] == "measured"
                    ]
                    visible = [
                        row["first_visible_seconds"]
                        for row in samples
                        if row["first_visible_seconds"] is not None
                    ]
                    result["models"][model][phase + "_summary"] = {
                        "measured": len(samples),
                        "failures": repetitions * len(cases) - len(samples),
                        "schema_valid": sum(row["schema_valid"] for row in samples),
                        "lexical_rubric_passes": sum(row["lexical_rubric_pass"] for row in samples),
                        "median_first_visible_seconds": statistics.median(visible)
                        if visible
                        else None,
                        "median_completion_seconds": statistics.median(
                            row["completion_seconds"] for row in samples
                        )
                        if samples
                        else None,
                    }
            finally:
                unload(model)
                save()
    return result
