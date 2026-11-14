import json

from sentio.evaluation.metrics import bootstrap_interval, ndcg, paired_bootstrap_p
from sentio.evaluation.public_retrieval import load_scifact, load_sciq
from sentio.rag.bm25 import BM25Searcher
from sentio.rag.knowledge_base import fuse_candidates
from sentio.rag.reranker import HybridRanker

CHUNKS = {
    "force": {"chunk_id": "force", "text_content": "An external net force changes motion."},
    "heat": {"chunk_id": "heat", "text_content": "Heat flows from hot objects to cold ones."},
    "stack": {"chunk_id": "stack", "text_content": "A stack is last in, first out."},
}


def fuse(query, vector_results, **switches):
    searcher = BM25Searcher()
    searcher.index(list(CHUNKS.values()))
    ranked = fuse_candidates(
        query, vector_results, searcher.search(query, limit=20), searcher, CHUNKS, HybridRanker(),
        **switches,
    )  # fmt: skip
    return [hit["id"] for hit in ranked]


def test_a_paraphrase_under_the_similarity_floor_is_dropped_by_default():
    query = "Which influence alters velocity?"
    vector_results = [{"id": "force", "score": 0.32}, {"id": "heat", "score": 0.05}]
    assert fuse(query, vector_results) == []
    assert fuse(query, vector_results, floor=-1.0, gate=False) == ["force", "heat"]


def test_keyword_only_candidates_are_kept_and_unknown_vector_ids_ignored():
    vector_results = [{"id": "deleted-chunk", "score": 0.9}]
    assert fuse("What changes motion?", vector_results) == ["force"]


def test_a_strong_vector_hit_outranks_a_weak_keyword_match():
    vector_results = [{"id": "heat", "score": 0.8}, {"id": "stack", "score": 0.4}]
    assert fuse("Where does heat go, first of all?", vector_results)[0] == "heat"


def test_ndcg_rewards_rank_and_bootstrap_helpers_are_deterministic():
    assert ndcg(["a", "b"], {"a"}) == 1.0
    assert 0 < ndcg(["b", "a"], {"a"}) < 1
    assert ndcg(["b"], {"a"}) == 0.0
    low, high = bootstrap_interval([0.0, 1.0, 1.0, 1.0])
    assert 0 <= low <= 0.75 <= high <= 1
    assert paired_bootstrap_p([1.0, 0.0, 1.0], [1.0, 0.0, 1.0]) == 1.0


def test_public_dataset_loaders_build_queries_and_gold_passages(tmp_path):
    sciq = tmp_path / "sciq"
    sciq.mkdir()
    item = {"question": "What is ice?", "support": "Ice is frozen water.", "correct_answer": "x"}
    for split in ("train", "valid"):
        (sciq / f"{split}.json").write_text("[]", encoding="utf-8")
    (sciq / "test.json").write_text(json.dumps([item, {**item, "support": ""}]), encoding="utf-8")
    dataset = load_sciq(tmp_path)
    assert dataset.queries == {"q0": "What is ice?"}
    assert dataset.corpus[next(iter(dataset.relevant["q0"]))] == "Ice is frozen water."

    scifact = tmp_path / "scifact"
    (scifact / "qrels").mkdir(parents=True)
    (scifact / "corpus.jsonl").write_text(
        json.dumps({"_id": "7", "title": "Ice", "text": "Frozen water."}) + "\n", encoding="utf-8"
    )
    (scifact / "queries.jsonl").write_text(
        json.dumps({"_id": "1", "text": "Ice is water."})
        + "\n"
        + json.dumps({"_id": "2", "text": "Unjudged."})
        + "\n",
        encoding="utf-8",
    )
    (scifact / "qrels" / "test.tsv").write_text(
        "query-id\tcorpus-id\tscore\n1\t7\t1\n", encoding="utf-8"
    )
    dataset = load_scifact(tmp_path)
    assert dataset.queries == {"1": "Ice is water."}
    assert dataset.corpus["7"] == "Ice Frozen water."
    assert dataset.relevant == {"1": {"7"}}
