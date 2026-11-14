"""Compare retrieval methods on SciQ or SciFact, using the tutor's own retrieval code.

The first model is the tutor's embedding model and runs every method. Further models run
dense search and rank fusion only, to show what the choice of embedding model is worth.
"""

import argparse
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from sentio.config import nlp_cfg
from sentio.evaluation.public_retrieval import (
    CANDIDATES,
    LOADERS,
    METHODS,
    Index,
    floor_effect,
    measure,
    summarise,
)
from sentio.rag.reranker import HybridRanker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(LOADERS), required=True)
    parser.add_argument("--data", type=Path, default=Path("datasets/public"))
    parser.add_argument("--models", nargs="+", default=[nlp_cfg.EMBEDDING_MODEL])
    parser.add_argument("--limit", type=int, help="only the first N queries")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.models[0] != nlp_cfg.EMBEDDING_MODEL:
        parser.error(f"the first model must be the tutor's own ({nlp_cfg.EMBEDDING_MODEL})")

    dataset = LOADERS[args.dataset](args.data)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset.name,
        "passages": len(dataset.corpus),
        "tutor_settings": {
            "embedding_model": nlp_cfg.EMBEDDING_MODEL,
            "candidates_per_retriever": CANDIDATES,
            "vector_weight": HybridRanker().w_vector,
            "keyword_weight": HybridRanker().w_keyword,
        },
        "packages": {name: version(name) for name in ("sentence-transformers", "torch", "numpy")},
        "platform": platform.platform(),
        "models": {},
    }
    baseline = None
    for position, model in enumerate(args.models):
        methods = list(METHODS) if position == 0 else ["dense", "rank_fusion"]
        print(f"{model}: {', '.join(methods)}", flush=True)
        index = Index(dataset, model, args.data / "cache")
        queries, rows, gold_similarity = measure(index, methods, args.limit)
        if baseline is None:
            baseline = rows["hybrid"]["ndcg_at_10"]
            report["queries"] = len(queries)
            report["keyword_index_build_ms"] = round(index.bm25_build_ms, 1)
        report["models"][model] = {
            "methods": summarise(rows, baseline),
            "similarity_floor": floor_effect(gold_similarity),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for model, result in report["models"].items():
        for name, entry in result["methods"].items():
            score = entry["ndcg_at_10"]
            print(
                f"{model:28} {name:18} nDCG@10 {score['mean']:.3f} "
                f"[{score['interval_95'][0]:.3f}, {score['interval_95'][1]:.3f}]  "
                f"hit@5 {entry['hit_at_5']['mean']:.3f}  "
                f"p {entry.get('p_against_hybrid', float('nan')):.3f}  "
                f"{entry['query_ms']['median']:.0f} ms"
            )
        print(f"{model:28} similarity floor: {result['similarity_floor']}")
    print(f"Keyword index build: {report['keyword_index_build_ms']} ms. Saved {args.output}")


if __name__ == "__main__":
    main()
