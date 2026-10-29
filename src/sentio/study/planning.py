"""Revision priorities from saved evidence, without an AI provider."""

import hashlib
from datetime import date, datetime, time, timedelta

from sentio.repositories.planning import PlanningRepository


class PlanningService:
    def __init__(self, engine):
        self.repository = PlanningRepository(engine)

    def daily_plan(self, owner, day=None, persist=True):
        day = day or date.today()
        saved = self.repository.plan(owner, day)
        if saved:
            return saved
        minutes = self.repository.preferences(owner)["daily_minutes"]
        before = datetime.combine(day + timedelta(days=1), time.min).timestamp()
        candidates = self.repository.candidates(owner, before)
        proposed = []
        for row in candidates["due"]:
            proposed.append(
                (
                    "review",
                    row["topic_id"],
                    f"Review due cards: {row['topic_id']}",
                    5,
                    row["evidence_count"],
                    "#/flashcards",
                )
            )
        for row in candidates["weak"]:
            proposed.append(
                (
                    "practice",
                    row["topic_id"],
                    f"Practise a weak area: {row['topic_id']}",
                    10,
                    row["evidence_count"],
                    "#/quizzes",
                )
            )
        for row in candidates["goals"]:
            proposed.append(("goal", row["goal_id"], row["goal_text"], 15, 0, "#/tutor"))
        if not proposed:
            proposed.append(
                ("study", "notes", "Choose notes and explain one concept", 15, 0, "#/documents")
            )
        remaining = minutes
        tasks = []
        for kind, reference, title, duration, count, destination in proposed:
            if remaining < 5 or len(tasks) >= 6:
                break
            duration = min(duration, remaining)
            task_id = hashlib.sha256(f"{owner}:{day}:{kind}:{reference}".encode()).hexdigest()[:24]
            tasks.append(
                {
                    "task_id": task_id,
                    "kind": kind,
                    "reference": reference,
                    "title": title,
                    "minutes": duration,
                    "evidence_count": count,
                    "destination": destination,
                    "completed_at": None,
                    "completion_evidence": "self_reported",
                }
            )
            remaining -= duration
        if persist:
            return self.repository.save_plan(owner, day, minutes, tasks)
        return {"day": str(day), "budget_minutes": minutes, "tasks": tasks}

    def feedback(self, owner):
        attempts, correct, last_attempt, mistakes = self.repository.feedback(owner)
        summary = (
            f"{correct} correct out of {attempts} saved quiz attempts. This is practice evidence, not a validated measure of mastery."
            if attempts
            else "Not assessed yet. Complete source-based practice to identify review priorities."
        )
        return {
            "attempts": attempts,
            "correct": correct,
            "accuracy": correct / attempts if attempts else None,
            "last_attempt_at": last_attempt,
            "mistakes": mistakes,
            "summary": summary,
        }
