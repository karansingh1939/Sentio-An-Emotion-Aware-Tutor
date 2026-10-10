import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.getcwd())

from sentio.tutor.tutor_agent import TutorAgent


def benchmark_ollama_5runs():
    print("=========================================================")
    print(" SENTIO OLLAMA CPU BENCHMARK (5 REPETITIONS PER PROMPT)")
    print("=========================================================")

    agent = TutorAgent()
    t0_start = time.perf_counter()
    agent.load()
    load_time_sec = time.perf_counter() - t0_start
    print(f"[*] Agent Subsystem Load Time: {load_time_sec:.2f} s")

    session = agent.start_session(
        "bench_student_5", "computer_science", "recursion", "intermediate"
    )
    session_id = session.session_id

    prompts = [
        ("Prompt 1 (Simple Factual)", "Define a function in Python."),
        ("Prompt 2 (RAG Retrieval)", "What is recursion according to the curriculum?"),
        (
            "Prompt 3 (Complex Tutoring)",
            "Explain the difference between iteration and recursion, provide pseudocode for both, and compare their stack memory consumption.",
        ),
    ]

    all_results = {}

    for label, prompt_text in prompts:
        print(f"\n--- Benchmarking: {label} (5 Runs) ---")
        runs = []
        for run_idx in range(1, 6):
            t0 = time.perf_counter()

            # Measure RAG retrieval time
            t0_rag = time.perf_counter()
            agent.kb.retrieve(
                subject="computer_science",
                topic="recursion",
                difficulty="intermediate",
                learning_state="neutral",
                query=prompt_text,
                session_id=session_id,
            )
            rag_latency_ms = (time.perf_counter() - t0_rag) * 1000.0

            # Execute chat
            t0_chat = time.perf_counter()
            res = agent.chat(session_id=session_id, student_message=prompt_text, frame=None)
            chat_latency_sec = time.perf_counter() - t0_chat
            total_latency_sec = time.perf_counter() - t0

            output_text = res.tutor_response.text if hasattr(res, "tutor_response") else ""
            char_count = len(output_text)
            est_tokens = max(1, len(output_text.split()) * 1.3)
            tps = est_tokens / max(0.1, chat_latency_sec)

            run_data = {
                "run": run_idx,
                "total_latency_sec": round(total_latency_sec, 2),
                "chat_latency_sec": round(chat_latency_sec, 2),
                "rag_latency_ms": round(rag_latency_ms, 2),
                "output_chars": char_count,
                "est_tokens": round(est_tokens, 1),
                "tokens_per_sec": round(tps, 2),
            }
            runs.append(run_data)
            print(
                f"  Run {run_idx}/5: Latency = {total_latency_sec:.2f}s | Output = {char_count} chars (~{est_tokens:.0f} tokens) | Speed = {tps:.2f} tok/s | RAG = {rag_latency_ms:.1f}ms"
            )

        latencies = [r["total_latency_sec"] for r in runs]
        tps_list = [r["tokens_per_sec"] for r in runs]

        all_results[label] = {
            "prompt": prompt_text,
            "runs": runs,
            "latency_min_sec": round(float(np.min(latencies)), 2),
            "latency_max_sec": round(float(np.max(latencies)), 2),
            "latency_avg_sec": round(float(np.mean(latencies)), 2),
            "latency_median_sec": round(float(np.median(latencies)), 2),
            "tps_avg": round(float(np.mean(tps_list)), 2),
        }

    agent.sm.close_session(session_id)

    summary = {"load_time_sec": round(load_time_sec, 2), "benchmark_prompts": all_results}

    os.makedirs("logs", exist_ok=True)
    with open("logs/ollama_cpu_benchmark_5runs.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n=========================================================")
    print(" BENCHMARK 5-RUN SUMMARY")
    print("=========================================================")
    for k, v in all_results.items():
        print(
            f"  {k}: Avg = {v['latency_avg_sec']}s (Min: {v['latency_min_sec']}s, Max: {v['latency_max_sec']}s, Median: {v['latency_median_sec']}s) | Speed: {v['tps_avg']} tok/s"
        )
    print("=========================================================")

    return summary


if __name__ == "__main__":
    benchmark_ollama_5runs()
