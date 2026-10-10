"""Fresh-context CPU inference experiments; never mutate a learner session."""

import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests

from sentio.ai.prompts import PromptBuilder, compact_evaluation_prompt
from sentio.config import nlp_cfg
from sentio.rag.knowledge_base import RetrievedContent

PROFILES = {
    "baseline": {"compact": False, "history_turns": 6, "max_tokens": 1024},
    "short_prompt": {"compact": True, "history_turns": 6, "max_tokens": 1024},
    "short_history": {"compact": False, "history_turns": 3, "max_tokens": 1024},
    "token_limit": {"compact": False, "history_turns": 6, "max_tokens": 256},
}


def messages_for(case, source, profile):
    context = f"[{case['expected_document']} Page 1]\n{source}"
    if profile["compact"]:
        system = compact_evaluation_prompt(context)
    else:
        content = RetrievedContent(
            subject="general",
            topic="evaluation",
            difficulty="beginner",
            learning_state="neutral",
            strategy="standard",
        )
        content.is_rag = True
        content.rag_context = context
        system = PromptBuilder().build_system_prompt(
            "general", "evaluation", "beginner", "neutral", "standard", "Patient and clear", content
        )
    history = [
        {"role": role, "content": text}
        for _ in range(profile["history_turns"])
        for role, text in (
            ("user", "Please use the supplied source."),
            ("assistant", "I will explain using that source."),
        )
    ]
    return [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": case["query"]},
    ]


def quality_check(raw, case):
    """Conservative lexical rubric, not a semantic correctness/accuracy claim."""
    try:
        payload = json.loads(raw)
        text = payload.get("text", "")
        if not isinstance(text, str):
            return False
        normalized = " ".join(text.lower().split())
        return (
            case["support"].lower() in normalized
            and case["expected_document"].lower() in normalized
        )
    except (ValueError, AttributeError):
        return False


def measure(client, case, messages, profile, phase, repetition):
    started = time.perf_counter()
    response = client.post(
        f"{nlp_cfg.OLLAMA_BASE_URL}/api/chat",
        json={
            "model": nlp_cfg.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "keep_alive": "15m",
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_predict": profile["max_tokens"],
                "num_gpu": 0,
            },
        },
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("message", {}).get("content", "")
    return {
        "case_id": case["id"],
        "phase": phase,
        "repetition": repetition,
        "latency_seconds": time.perf_counter() - started,
        "quality_pass": quality_check(text, case),
        "output": text,
        "done_reason": data.get("done_reason"),
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": data.get("eval_count"),
        "load_seconds": data.get("load_duration", 0) / 1e9,
        "messages": messages,
    }


def cold_runs(client, cases, dataset_dir, results):
    # Unload before each cold measurement; OS file cache is not cleared.
    for name, profile in PROFILES.items():
        unloaded = client.post(
            f"{nlp_cfg.OLLAMA_BASE_URL}/api/generate",
            json={"model": nlp_cfg.OLLAMA_MODEL, "keep_alive": 0},
            timeout=180,
        )
        unloaded.raise_for_status()
        case = cases[0]
        messages = messages_for(
            case, (dataset_dir / case["expected_document"]).read_text(), profile
        )
        results[name]["runs"].append(measure(client, case, messages, profile, "cold", 0))


def warm_runs(client, cases, dataset_dir, results, repetitions):
    for repetition in range(repetitions):
        names = list(PROFILES)
        names = names[repetition % len(names) :] + names[: repetition % len(names)]
        for case in cases:
            source = (dataset_dir / case["expected_document"]).read_text()
            for name in names:
                profile = PROFILES[name]
                row = measure(
                    client,
                    case,
                    messages_for(case, source, profile),
                    profile,
                    "warm",
                    repetition + 1,
                )
                results[name]["runs"].append(row)
                print(
                    f"{name} {case['id']} repetition {repetition + 1}: {row['latency_seconds']:.2f}s, rubric={row['quality_pass']}",
                    flush=True,
                )


def benchmark(dataset_dir, repetitions=3, case_count=3):
    if repetitions < 3:
        raise ValueError("Use at least three repetitions for each equivalent prompt.")
    dataset_dir = Path(dataset_dir)
    dataset = json.loads((dataset_dir / "dataset.json").read_text())
    answerable = [c for c in dataset["queries"] if c["kind"] == "answerable"]
    cases = answerable[:case_count]
    if not cases:
        raise ValueError("No answerable evaluation cases selected.")
    with requests.Session() as client:
        tags = client.get(f"{nlp_cfg.OLLAMA_BASE_URL}/api/tags", timeout=5).json()
        model = next(m for m in tags["models"] if m["name"] == nlp_cfg.OLLAMA_MODEL)
        results = {name: {"configuration": cfg, "runs": []} for name, cfg in PROFILES.items()}
        cold_runs(client, cases, dataset_dir, results)
        warm_runs(client, cases, dataset_dir, results, repetitions)
        for data in results.values():
            warm = [r for r in data["runs"] if r["phase"] == "warm"]
            data["summary"] = {
                "median_warm_seconds": statistics.median(r["latency_seconds"] for r in warm),
                "mean_warm_seconds": statistics.mean(r["latency_seconds"] for r in warm),
                "rubric_passes": sum(r["quality_pass"] for r in warm),
                "warm_samples": len(warm),
            }
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset_version": dataset["version"],
            "model": model["name"],
            "model_digest": model["digest"],
            "hardware": {
                "platform": platform.platform(),
                "cpu": platform.processor(),
                "logical_cpus": psutil.cpu_count(),
                "ram_bytes": psutil.virtual_memory().total,
            },
            "configuration": {
                "num_gpu": 0,
                "seed": 42,
                "temperature": 0,
                "timeout_seconds": 180,
                "fresh_messages": True,
            },
            "limitations": [
                "Small synthetic sample; lexical rubric is not semantic grading.",
                "Cold means Ollama model reload, not cleared OS disk cache.",
                "Provider inference only; excludes retrieval, HTTP application and UI latency.",
            ],
            "profiles": results,
        }
