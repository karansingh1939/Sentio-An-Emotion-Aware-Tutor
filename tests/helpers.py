"""Deterministic provider responses and real authentication for integration tests."""

import json
import re
import uuid


def login_student(client, *, admin=False):
    from sentio.api.app import PREFIX, agent

    body = {"email": f"test-{uuid.uuid4().hex}@example.com", "password": "StrongPassword123!"}
    response = client.post(PREFIX + "/auth/register", json=body)
    assert response.status_code == 201, response.text
    student_id = response.json()["student_id"]
    if admin:
        account = agent.sm.persister.auth_repo.get_account_by_student_id(student_id)
        account.role = "admin"
        agent.sm.persister.auth_repo.save_account(account)
    response = client.post(PREFIX + "/auth/login", json=body)
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return student_id


def upload_notes(client, text, name="notes.txt"):
    """Upload a notes file as the logged-in student and return its document id."""
    from sentio.api.app import PREFIX

    response = client.post(
        PREFIX + "/documents/upload", files={"file": (name, text.encode(), "text/plain")}
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def index_notes(agent, owner, text, name="notes.txt"):
    """Index a small notes file for an owner directly (no HTTP) and return its document id."""
    import tempfile
    from pathlib import Path

    from sentio.ingestion.pipeline import DocumentIngestionPipeline

    folder = Path(tempfile.mkdtemp(prefix="sentio-notes-"))
    path = folder / name
    path.write_text(text, encoding="utf-8")
    pipeline = DocumentIngestionPipeline(sm=agent.sm, vdb=agent.kb.vdb)
    pipeline.load()
    assert pipeline.process_file(path, "notes", None, student_id=owner), pipeline.last_error
    return agent.sm.get_document_by_filename(name, student_id=owner, category="notes")["id"]


def complete(system_prompt, history, user_message, **kwargs):
    prompt = system_prompt.lower()
    requested = re.search(r"exactly (\d+) (?:questions|flashcards)", prompt)
    count = int(requested[1]) if requested else 3
    if "generate a quiz" in prompt:
        questions = [
            dict(
                question_text="Which quantity measures disorder?",
                question_type="multiple_choice",
                options=["Entropy", "Energy", "Temperature", "Pressure"],
                correct_answer="Entropy",
            ),
            dict(
                question_text="Energy is conserved.",
                question_type="true_false",
                options=["True", "False"],
                correct_answer="True",
            ),
            dict(
                question_text="What does a thermometer measure?",
                question_type="short_answer",
                options=None,
                correct_answer="temperature",
            ),
        ]
        for question in questions:
            question.update(
                explanation="A thermodynamics concept.",
                difficulty="intermediate",
                topic="thermodynamics",
            )
        questions = [questions[i % len(questions)] for i in range(count)]
        return json.dumps({"title": "Thermodynamics", "questions": questions}), 100
    if "flashcards about" in prompt:
        cards = [
            dict(front=term, back="A thermodynamics concept.", tags=["thermodynamics"])
            for term in ["Entropy", "Energy", "Temperature"]
        ]
        cards = [cards[i % len(cards)] for i in range(count)]
        return json.dumps({"deck_name": "Thermodynamics", "cards": cards}), 50
    if "grade" in prompt:
        return json.dumps({"is_correct": False, "score": 0.0}), 10
    if "summary of student performance" in prompt:
        return "Keep practicing the concepts you missed.", 10
    return json.dumps(
        {
            "text": "Let's explore this concept.",
            "follow_up_question": "What do you think?",
            "encouragement": "Keep going!",
            "suggested_topic": "thermodynamics",
        }
    ), 30


async def auto_answer_dialogs(page, text):
    """Accept every in-page dialog, typing `text` into text dialogs.

    Stands in for Playwright's page.on("dialog") now that the app uses in-page dialogs
    instead of window.prompt and window.confirm.
    """
    await page.add_init_script(
        """text => new MutationObserver(() => {
            const modal = [...document.querySelectorAll('sentio-modal')].at(-1);
            if (!modal || modal.dataset.autoAnswered) return;
            const input = modal.querySelector('#dialog-text');
            const ok = modal.querySelector('[data-dialog-ok], .dialog-form [type=submit]');
            if (!ok) return;
            modal.dataset.autoAnswered = '1';
            if (input) input.value = text;
            setTimeout(() => ok.click(), 0);
        }).observe(document, { childList: true, subtree: true })""".replace(
            "text =>", "(text => "
        ).rstrip()
        + f")({text!r})"
    )
