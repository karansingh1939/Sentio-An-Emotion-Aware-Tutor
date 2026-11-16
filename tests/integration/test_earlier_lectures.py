"""A lecture can rely on what an earlier lecture taught; the tutor should find it there."""

import json
import re

import pytest

from sentio.repositories.courses import lecture_number


@pytest.mark.parametrize(
    "filename, number",
    [
        ("1. Introduction.pptx", 1),
        ("02_cnn.pdf", 2),
        ("Lecture 3 - Pooling.pdf", 3),
        ("L4 slides.pptx", 4),
        ("week-5 notes.docx", 5),
        ("CSET225 syllabus.pdf", None),
        ("IntroMlSvmCnn.pdf", None),
    ],
)
def test_lecture_numbers_are_read_from_common_filename_styles(filename, number):
    assert lecture_number(filename) == number


KINEMATICS = (
    b"Average velocity equals total displacement divided by total time taken. "
    b"Displacement is measured in metres and time in seconds."
)
PROJECTILES = (
    b"A projectile follows a curved path under gravity. Its horizontal motion "
    b"uses the average velocity from the previous class to find the range."
)
LATER = b"Average velocity of a rotating body is replaced by angular velocity in this class."


def _course_with_lectures(client):
    course = client.post("/api/v1/courses", json={"name": "physics"}).json()
    ids = {}
    for name, body in [
        ("1. Kinematics.txt", KINEMATICS),
        ("2. Projectiles.txt", PROJECTILES),
        ("3. Rotation.txt", LATER),
    ]:
        uploaded = client.post(
            "/api/v1/documents/upload",
            params={"course_id": course["id"]},
            files={"file": (name, body, "text/plain")},
        )
        assert uploaded.status_code == 201, uploaded.text
        ids[name] = uploaded.json()["document_id"]
    return ids


def _session(client, document_id):
    return client.post(
        "/api/v1/sessions",
        json={
            "student_id": "ignored",
            "subject": "physics",
            "topic": "motion",
            "difficulty": "beginner",
            "metadata": {"document_id": document_id},
        },
    ).json()["session_id"]


def test_earlier_lectures_are_ordered_by_number_and_exclude_later_ones():
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from sentio.repositories.courses import earlier_lectures
    from tests.helpers import login_student

    with TestClient(app) as client:
        owner = login_student(client)
        ids = _course_with_lectures(client)
        with agent.sm.persister._engine.connect() as connection:
            assert earlier_lectures(connection, owner, ids["3. Rotation.txt"]) == [
                ids["2. Projectiles.txt"],
                ids["1. Kinematics.txt"],
            ]
            assert earlier_lectures(connection, owner, ids["1. Kinematics.txt"]) == []
            # Someone else's lecture ids reveal nothing.
            assert earlier_lectures(connection, "someone-else", ids["3. Rotation.txt"]) == []


def test_a_question_no_lecture_so_far_covers_says_so_without_calling_the_model(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from tests.helpers import login_student

    with TestClient(app) as client:
        login_student(client)
        ids = _course_with_lectures(client)
        sid = _session(client, ids["2. Projectiles.txt"])
        monkeypatch.setattr(agent.kb.vdb, "search", lambda *args, **kwargs: [])

        def forbidden(**kwargs):
            raise AssertionError("Unsupported questions must not reach the model")

        monkeypatch.setattr(agent.nlp._backend, "complete", forbidden)
        result = client.post(
            f"/api/v1/sessions/{sid}/chat/stream",
            json={
                "message": "What is the boiling point of ethanol?",
                "request_id": "nowhere-covered",
            },
        )
        assert "event: complete" in result.text, result.text
        assert "Neither this lecture nor the earlier lectures" in result.text


def _ask(client, monkeypatch, complete, document_name, question, request_id):
    from sentio.api.app import agent

    ids = _course_with_lectures(client)
    sid = _session(client, ids[document_name])
    monkeypatch.setattr(agent.nlp._backend, "complete", complete)
    result = client.post(
        f"/api/v1/sessions/{sid}/chat/stream",
        json={"message": question, "request_id": request_id},
    )
    complete_event = result.text.split("event: complete", 1)[1]
    return json.loads(complete_event.split("data: ", 1)[1].split("\n", 1)[0])


def _reference(user_message, filename):
    pattern = r"\[" + re.escape(filename) + r" Page [^\]]+\]"
    return re.search(pattern, user_message).group(0)


def test_the_selected_and_earlier_lectures_are_searched_in_one_ranking(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import app
    from tests.helpers import login_student

    prompts = []

    def complete(system_prompt, history, user_message, **kwargs):
        prompts.append(user_message)
        reference = _reference(user_message, "1. Kinematics.txt")
        text = f"Average velocity is total displacement divided by total time {reference}."
        return json.dumps({"text": text}), 12

    with TestClient(app) as client:
        login_student(client)
        data = _ask(
            client,
            monkeypatch,
            complete,
            "2. Projectiles.txt",
            "What is the formula for average velocity?",
            "one-ranking",
        )
    assert len(prompts) == 1, "one model call, not a retry"
    assert data["text"].startswith(
        "Your selected lecture doesn't cover this, but an earlier lecture does (1. Kinematics.txt)."
    )
    # A later lecture is never searched.
    assert "angular velocity" not in prompts[0]
    assert "3. Rotation.txt" not in {source["filename"] for source in data["source_citations"]}


def test_an_answer_citing_both_lectures_says_it_builds_on_the_earlier_one(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import app
    from tests.helpers import login_student

    def complete(system_prompt, history, user_message, **kwargs):
        earlier = _reference(user_message, "1. Kinematics.txt")
        selected = _reference(user_message, "2. Projectiles.txt")
        text = (
            f"The range uses average velocity {selected}, which is displacement over time "
            f"{earlier}."
        )
        return json.dumps({"text": text}), 12

    with TestClient(app) as client:
        login_student(client)
        data = _ask(
            client,
            monkeypatch,
            complete,
            "2. Projectiles.txt",
            "How is the range found using average velocity?",
            "builds-on-earlier",
        )
    assert data["text"].startswith("This builds on an earlier lecture (1. Kinematics.txt).")


def test_an_admission_part_way_through_a_reply_becomes_a_plain_refusal(monkeypatch):
    from fastapi.testclient import TestClient

    from sentio.api.app import app
    from tests.helpers import login_student

    def complete(system_prompt, history, user_message, **kwargs):
        reference = _reference(user_message, "2. Projectiles.txt")
        text = (
            "Average velocity is speed with a direction. These notes do not contain "
            f"enough information to say more. {reference}"
        )
        return json.dumps({"text": text}), 9

    with TestClient(app) as client:
        login_student(client)
        data = _ask(
            client,
            monkeypatch,
            complete,
            "2. Projectiles.txt",
            "What is the average velocity?",
            "midway-admits",
        )
    assert data["text"].startswith("Neither this lecture nor the earlier lectures")
    assert "speed with a direction" not in data["text"]
