import json

import pytest
from sqlalchemy import text

from sentio.ingestion.recovery import DocumentRecovery
from tests.test_ingestion_resilience import pipeline as pipeline_fixture

pipeline = pipeline_fixture


@pytest.fixture
def material(pipeline, tmp_path):
    root = tmp_path / "documents"
    path = root / "owner" / "notes" / "guide.txt"
    path.parent.mkdir(parents=True)
    path.write_text("An original explanation of inertia.", encoding="utf-8")
    assert pipeline.process_file(path, "notes", "physics", "owner")
    journal = DocumentRecovery(pipeline.sm.persister, pipeline.vdb, root, require_owner=False)
    document = pipeline.sm.list_documents(student_id="owner")[0]
    return pipeline, journal, path, document


def staged(path, content):
    stage = path.parent / ".pending-test"
    stage.mkdir(exist_ok=True)
    pending = stage / path.name
    pending.write_text(content, encoding="utf-8")
    return pending


def test_terminal_journals_are_bounded_without_losing_pending_recovery(material):
    import time

    pipeline, journal, _, _ = material
    now = time.time()
    with pipeline.sm.persister._engine.begin() as connection:
        rows = [
            {"id": f"done-{index}", "status": "completed", "created": now + index / 1000}
            for index in range(510)
        ]
        rows.extend(
            [
                {"id": "old-completed", "status": "completed", "created": now - 8 * 86400},
                {"id": "old-pending", "status": "pending", "created": now - 8 * 86400},
            ]
        )
        connection.execute(
            text("""INSERT INTO recovery_operations
            (operation_id,student_id,kind,payload_json,status,created_at)
            VALUES (:id,'owner','replace','{}',:status,:created)"""),
            rows,
        )
    journal.prune()
    with pipeline.sm.persister._engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM recovery_operations WHERE status='completed'")
            ).scalar()
            == 500
        )
        assert (
            connection.execute(
                text("SELECT status FROM recovery_operations WHERE operation_id='old-pending'")
            ).scalar()
            == "pending"
        )


def test_failed_sql_publication_restores_original_file_and_chunks(material, monkeypatch):
    pipeline, journal, path, document = material
    previous_chunks = pipeline.sm.get_document_chunks(document["id"])
    pending = staged(path, "A replacement explanation of inertia.")
    monkeypatch.setattr(
        journal.repository,
        "replace",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("database write failed")),
    )
    assert not pipeline.process_file(
        pending,
        "notes",
        "physics",
        "owner",
        publisher=lambda doc, chunks, old: journal.replace(pending, path, doc, chunks, old),
    )
    assert path.read_text() == "An original explanation of inertia."
    assert pipeline.sm.list_documents(student_id="owner")[0] == document
    assert pipeline.sm.get_document_chunks(document["id"]) == previous_chunks


def test_startup_rolls_back_file_move_without_sql_commit(material):
    pipeline, journal, path, document = material
    payload = {
        "document_id": document["id"],
        "checksum": "uncommitted",
        "destination": str(path),
        "had_file": True,
        "old_chunk_ids": [],
    }
    _, backup = journal._start("owner", "replace", payload)
    path.replace(backup)
    staged(path, "Not yet committed").replace(path)
    assert journal.recover()["recovered"] == 1
    assert path.read_text() == "An original explanation of inertia."
    assert pipeline.sm.list_documents(student_id="owner")[0] == document


def test_cleanup_failure_then_new_replacement_never_restores_stale_file(material):
    pipeline, journal, path, document = material
    pipeline.vdb.delete_chunk_points.return_value = False
    for content in ["Revision two evidence.", "Revision three evidence."]:
        pending = staged(path, content)
        assert pipeline.process_file(
            pending,
            "notes",
            "physics",
            "owner",
            publisher=lambda doc, chunks, old: journal.replace(pending, path, doc, chunks, old),
        )
    pipeline.vdb.delete_chunk_points.return_value = True
    journal.recover()
    assert path.read_text() == "Revision three evidence."
    chunks = pipeline.sm.get_document_chunks(document["id"])
    assert chunks[0]["text_content"] == "Revision three evidence."
    active_ids = {c["chunk_id"] for c in chunks}
    for call in pipeline.vdb.delete_chunk_points.call_args_list[-2:]:
        assert not active_ids.intersection(call.args[0])


def test_failed_deletion_keeps_file_and_registered_evidence(material, monkeypatch):
    pipeline, journal, path, document = material
    monkeypatch.setattr(
        journal.repository, "remove", lambda *args: (_ for _ in ()).throw(OSError("write failed"))
    )
    with pytest.raises(OSError):
        journal.delete(document, path, pipeline.sm.get_document_chunks(document["id"]))
    assert path.exists()
    assert pipeline.sm.get_document_chunks(document["id"])


def test_recovery_rejects_paths_outside_the_owner_directory(material, tmp_path):
    pipeline, journal, path, document = material
    outside = tmp_path / "private-other.txt"
    outside.write_text("Must stay intact")
    payload = {
        "document_id": document["id"],
        "checksum": "uncommitted",
        "destination": str(outside),
        "backup": str(outside),
        "had_file": True,
        "old_chunk_ids": [],
        "previous_checksum": document["checksum"],
        "previous_file_hash": "",
    }
    with pipeline.sm.persister._engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO recovery_operations VALUES ('unsafe','owner','replace',:payload,'pending',1,NULL)"
            ),
            {"payload": json.dumps(payload)},
        )
    assert journal.recover()["pending"] == 1
    assert outside.read_text() == "Must stay intact"


def test_partial_sql_write_rolls_back_metadata_and_chunks(material, monkeypatch):
    pipeline, journal, path, document = material
    original = pipeline.sm.get_document_chunks(document["id"])
    pending = staged(path, "Replacement that must not be published.")
    monkeypatch.setattr(
        pipeline.sm.persister, "save_document_chunks", lambda *args, **kwargs: False
    )
    assert not pipeline.process_file(
        pending,
        "notes",
        "physics",
        "owner",
        publisher=lambda doc, chunks, old: journal.replace(pending, path, doc, chunks, old),
    )
    assert pipeline.sm.list_documents(student_id="owner")[0] == document
    assert pipeline.sm.get_document_chunks(document["id"]) == original
    assert path.read_text() == "An original explanation of inertia."


def test_cancel_after_vector_staging_preserves_published_revision(material):
    from sentio.jobs.control import WorkCancelled, WorkControl, execution

    pipeline, journal, path, document = material
    original = pipeline.sm.get_document_chunks(document["id"])
    control = WorkControl()
    pipeline.vdb.index_chunks.side_effect = lambda **kwargs: control.cancel() or True
    pending = staged(path, "Cancelled replacement evidence.")
    with execution(control), pytest.raises(WorkCancelled):
        pipeline.process_file(
            pending,
            "notes",
            "physics",
            "owner",
            publisher=lambda doc, chunks, old: journal.replace(pending, path, doc, chunks, old),
        )
    assert pipeline.sm.get_document_chunks(document["id"]) == original
    assert path.read_text() == "An original explanation of inertia."
    assert not {c["chunk_id"] for c in original}.intersection(
        pipeline.vdb.delete_chunk_points.call_args.args[0]
    )


def test_corrupt_recovery_record_does_not_block_startup(material):
    pipeline, journal, path, document = material
    with pipeline.sm.persister._engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO recovery_operations VALUES ('corrupt','owner','replace','{','pending',1,NULL)"
            )
        )
    assert journal.recover()["pending"] == 1
    assert path.read_text() == "An original explanation of inertia."
