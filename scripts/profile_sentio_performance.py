import os
import sys

sys.path.insert(0, os.getcwd())

import time

import numpy as np
from pyinstrument import Profiler

from sentio.ai.emotion_detector import EmotionDetector
from sentio.rag.knowledge_base import KnowledgeBase
from sentio.tutor.tutor_agent import TutorAgent


def run_performance_profiling():
    print("==================================================")
    print(" SENTIO PERFORMANCE PROFILING REPORT (PyInstrument)")
    print("==================================================")

    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    profile_html_path = os.path.join(logs_dir, "performance_profile.html")

    profiler = Profiler()
    profiler.start()

    # 1. Benchmark Emotion Detector Inference
    print("\n[1/4] Benchmarking Emotion Detector Model Inference...")
    t0 = time.time()
    detector = EmotionDetector()
    detector.load_model()
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for _ in range(5):
        _ = detector.predict_emotion(dummy_frame)
    t_emotion = (time.time() - t0) / 5.0
    print(f"-> Average Emotion Detection Frame Processing Time: {t_emotion * 1000:.2f} ms")

    # 2. Benchmark RAG Knowledge Base Retrieval Latency
    print("\n[2/4] Benchmarking RAG Knowledge Base Retrieval Latency...")
    t0 = time.time()
    kb = KnowledgeBase()
    retrieved = kb.retrieve(
        subject="computer_science",
        topic="recursion",
        difficulty="beginner",
        learning_state="neutral",
    )
    t_rag = (time.time() - t0) * 1000.0
    print(
        f"-> RAG Query Latency: {t_rag:.2f} ms (Retrieved: {retrieved.topic if retrieved else 'None'})"
    )

    # 3. Benchmark TutorAgent Initialization
    print("\n[3/4] Benchmarking TutorAgent Initialization...")
    t0 = time.time()
    agent = TutorAgent()
    agent.load()
    t_startup = (time.time() - t0) * 1000.0
    print(f"-> TutorAgent Load & System Health Check Time: {t_startup:.2f} ms")

    # 4. Benchmark Ollama NLP Coordinator Response
    print("\n[4/4] Benchmarking Ollama NLP Coordinator Response...")
    t0 = time.time()
    ollama_ok = getattr(agent.nlp, "backend_available", True)
    t_ollama = (time.time() - t0) * 1000.0
    print(f"-> Ollama Health Check Latency: {t_ollama:.2f} ms (Status: {ollama_ok})")

    profiler.stop()

    # Save HTML Profile
    with open(profile_html_path, "w", encoding="utf-8") as f:
        f.write(profiler.output_html())

    print("\n--------------------------------------------------")
    print(f"PyInstrument HTML Profile report saved to: {profile_html_path}")
    print("--------------------------------------------------")


if __name__ == "__main__":
    run_performance_profiling()
