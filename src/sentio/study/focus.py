"""What a study session without a topic of its own is about, for making practice."""

from sentio.repositories.topics import TopicRepository

TITLES_KEPT = 8


def _lectures(agent, student_id, document_id):
    """The indexed lectures a session studies from: one, a course's, or all of them."""
    if document_id == "all":
        return [
            document["id"]
            for document in agent.sm.list_documents(student_id=student_id)
            if document["status"] == "indexed"
        ]
    from sentio.repositories.courses import expand_source

    with agent.sm.persister._engine.connect() as connection:
        selected = expand_source(connection, student_id, document_id)
    return selected if isinstance(selected, list) else [selected]


def recent_questions(agent, session_id, kept=3):
    """The learner's last questions in this session, from the saved turns.

    The model's in-memory history is empty after a restart; saved turns are not.
    """
    from sqlalchemy import text

    with agent.sm.persister._engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT message FROM chat_requests WHERE session_id=:id AND status='complete' "
                "AND message!='' ORDER BY updated_at DESC LIMIT :kept"
            ),
            {"id": session_id, "kept": kept},
        ).scalars()
        saved = list(rows)[::-1]
    if saved:
        return saved
    history = agent.nlp._get_history(session_id).to_list()
    return [turn["content"] for turn in history if turn["role"] == "user"][-kept:]


def session_focus(agent, session_id, student_id, document_id, subject):
    """A search query and a label for practising a session that has no topic.

    The learner's recent questions say what the session was about; before any,
    the topics found in its lectures stand in.
    """
    asked = recent_questions(agent, session_id)
    if asked:
        return " ".join(asked), subject
    topics = TopicRepository(agent.sm.persister._engine)
    titles = []
    lectures = _lectures(agent, student_id, document_id)
    for lecture_id in lectures:
        lecture = topics.document_topics(student_id, lecture_id) or {}
        titles += [item["title"] for item in lecture.get("topics", [])][:3]
    if titles:
        return " ".join(titles[:TITLES_KEPT]), subject
    return subject, subject
