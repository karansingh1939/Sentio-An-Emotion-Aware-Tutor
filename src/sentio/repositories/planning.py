"""Owner-scoped persisted study preferences, goal changes and daily snapshots."""

import json
import time

from sqlalchemy import text

from sentio.shared.sqlite_tx import begin_immediate


def active_goal(connection, owner, goal_id):
    """The owner's active goal bound to study context, or None if absent, foreign or finished."""
    if not goal_id:
        return None
    row = (
        connection.execute(
            text(
                "SELECT goal_id,goal_text FROM learning_goals WHERE student_id=:owner AND goal_id=:goal AND status='active'"
            ),
            {"owner": owner, "goal": goal_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


class PlanningRepository:
    def __init__(self, engine):
        self.engine = engine

    def preferences(self, owner):
        with self.engine.connect() as connection:
            minutes = connection.execute(
                text("SELECT daily_minutes FROM study_preferences WHERE student_id=:owner"),
                {"owner": owner},
            ).scalar()
        return {"daily_minutes": minutes if minutes is not None else 30}

    def save_preferences(self, owner, minutes):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO study_preferences VALUES (:owner,:minutes,:now) ON CONFLICT(student_id) DO UPDATE SET daily_minutes=:minutes,updated_at=:now"
                ),
                {"owner": owner, "minutes": minutes, "now": time.time()},
            )
        return self.preferences(owner)

    def plan(self, owner, day):
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT budget_minutes,tasks_json,created_at FROM daily_plans WHERE student_id=:owner AND day=:day"
                ),
                {"owner": owner, "day": str(day)},
            ).first()
        if row is None:
            return None
        return {
            "day": str(day),
            "budget_minutes": row[0],
            "tasks": json.loads(row[1]),
            "created_at": row[2],
        }

    def save_plan(self, owner, day, minutes, tasks):
        with self.engine.begin() as connection:
            connection.execute(
                text("INSERT OR IGNORE INTO daily_plans VALUES (:owner,:day,:minutes,:tasks,:now)"),
                {
                    "owner": owner,
                    "day": str(day),
                    "minutes": minutes,
                    "tasks": json.dumps(tasks),
                    "now": time.time(),
                },
            )
        return self.plan(owner, day)

    def complete(self, owner, day, task_id, completed):
        with self.engine.begin() as connection:
            begin_immediate(connection)
            row = connection.execute(
                text("SELECT tasks_json FROM daily_plans WHERE student_id=:owner AND day=:day"),
                {"owner": owner, "day": str(day)},
            ).first()
            if row is None:
                return None
            tasks = json.loads(row[0])
            task = next((t for t in tasks if t["task_id"] == task_id), None)
            if task is None:
                return None
            task["completed_at"] = (task["completed_at"] or time.time()) if completed else None
            connection.execute(
                text(
                    "UPDATE daily_plans SET tasks_json=:tasks WHERE student_id=:owner AND day=:day"
                ),
                {"owner": owner, "day": str(day), "tasks": json.dumps(tasks)},
            )
        return self.plan(owner, day)

    def candidates(self, owner, review_before):
        with self.engine.connect() as connection:

            def rows(sql):
                return [
                    dict(row)
                    for row in connection.execute(
                        text(sql), {"owner": owner, "before": review_before}
                    ).mappings()
                ]

            return {
                "due": rows(
                    "SELECT topic_id,COUNT(*) AS evidence_count,MIN(next_review_at) AS oldest FROM flashcards WHERE student_id=:owner AND next_review_at<:before GROUP BY topic_id ORDER BY oldest,topic_id LIMIT 6"
                ),
                "weak": rows(
                    "SELECT topic_id,mastery_score,attempts_count AS evidence_count FROM student_knowledge WHERE student_id=:owner AND attempts_count>0 AND mastery_score<0.5 ORDER BY mastery_score,topic_id LIMIT 6"
                ),
                "goals": rows(
                    "SELECT goal_id,goal_text,topic_id,target_date FROM learning_goals WHERE student_id=:owner AND status='active' ORDER BY target_date IS NULL,target_date,created_at,goal_id LIMIT 6"
                ),
            }

    def feedback(self, owner):
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT COUNT(*),SUM(correct),MAX(timestamp) FROM quiz_attempts WHERE student_id=:owner"
                ),
                {"owner": owner},
            ).first()
            mistakes = [
                dict(r)
                for r in connection.execute(
                    text(
                        "SELECT topic,question_text,student_answer,timestamp FROM quiz_attempts WHERE student_id=:owner AND correct=0 ORDER BY timestamp DESC,id DESC LIMIT 10"
                    ),
                    {"owner": owner},
                ).mappings()
            ]
        return row[0], row[1] or 0, row[2], mistakes

    def update_goal(self, owner, goal_id, changes):
        with self.engine.begin() as connection:
            begin_immediate(connection)
            goal = (
                connection.execute(
                    text("SELECT * FROM learning_goals WHERE student_id=:owner AND goal_id=:goal"),
                    {"owner": owner, "goal": goal_id},
                )
                .mappings()
                .first()
            )
            if goal is None:
                return None
            updated = dict(goal)
            updated.update(changes)
            updated["completed_at"] = (
                (updated["completed_at"] or time.time())
                if updated["status"] == "completed"
                else None
            )
            connection.execute(
                text(
                    "UPDATE learning_goals SET goal_text=:goal_text,target_date=:target_date,status=:status,completed_at=:completed_at WHERE student_id=:student_id AND goal_id=:goal_id"
                ),
                updated,
            )
        return updated
