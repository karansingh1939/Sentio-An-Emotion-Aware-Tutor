"""Short overview of one document: summary, key concepts and questions to ask."""

from sentio.ai.prompts import overview_prompt
from sentio.ai.structured_parser import DocumentOverviewSchema, generate_structured
from sentio.jobs.control import checkpoint
from sentio.repositories.documents import DocumentRepository


def generate_overview(agent, owner, document_id):
    repository = DocumentRepository(agent.sm.persister)
    cached = repository.get_overview(document_id, owner)
    if cached:
        return cached
    checkpoint("reading your notes")
    preview = repository.preview(document_id, owner, limit=8)
    if not preview or not preview["chunks"]:
        raise ValueError("These notes have no readable text to summarize.")
    passages = "\n\n".join(chunk["text_content"] for chunk in preview["chunks"])[:6000]
    checkpoint("writing overview")
    overview = generate_structured(
        agent.nlp._backend,
        DocumentOverviewSchema,
        overview_prompt(passages),
        "Write the overview now.",
        temperature=0.3,
    )
    saved = repository.save_overview(document_id, owner, overview.model_dump())
    if saved is None:
        raise ValueError("These notes were deleted while the overview was written.")
    return saved
