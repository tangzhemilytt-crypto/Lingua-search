"""Retrieval evaluation for LinguaSearch.

Compares the offline lexical retriever with the hybrid (embedding + lexical)
retriever on a small labelled set: English paraphrase queries and Chinese
queries against English-only passages (true cross-language retrieval).

Usage (from the repository root, with the project's virtualenv active):

    python eval/run_eval.py                 # lexical, plus hybrid if OPENAI_API_KEY is set
    python eval/run_eval.py --mode lexical  # no API key needed
    python eval/run_eval.py --json eval/results.json

The hybrid run calls the OpenAI embeddings API for 12 passages and 24 queries,
which is a very small request. Results are only as meaningful as the dataset:
it is synthetic, tiny, and every query has exactly one relevant passage.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP_K = 5


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["lexical", "hybrid", "both"], default="both")
    parser.add_argument("--dataset", type=Path, default=HERE / "dataset.json")
    parser.add_argument(
        "--repo",
        type=Path,
        default=HERE.parent,
        help="Repository root that contains src/ (default: parent of eval/).",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=20,
        help="Lexical runs to average (default 20). Tied scores are ordered by "
        "random document UUIDs, so a single lexical run is not reproducible.",
    )
    parser.add_argument("--json", type=Path, help="Write the metrics to this file.")
    return parser.parse_args()


def evaluate(mode, dataset, modules, api_key):
    Settings, Store, Provider, retrieve = modules
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            database_path=str(Path(tmp) / "eval.db"),
            api_key=api_key if mode == "hybrid" else "",
        )
        store = Store(settings.database_path)
        for passage in dataset["passages"]:
            store.add(
                passage["id"],
                passage["id"] + ".txt",
                [(1, passage["text"])],
                "eval:" + passage["id"],
            )
        provider = Provider(settings)

        by_lang = {}
        for query in dataset["queries"]:
            results = retrieve(store, provider, settings, query["text"], [], TOP_K)
            titles = [r["title"] for r in results]
            rank = titles.index(query["relevant"]) + 1 if query["relevant"] in titles else None
            by_lang.setdefault(query["lang"], []).append(rank)
        return by_lang


def summarize(ranks, runs=1):
    total = len(ranks)
    return {
        "queries": total // runs,
        "recall@1": sum(1 for r in ranks if r == 1) / total,
        "recall@3": sum(1 for r in ranks if r is not None and r <= 3) / total,
        "mrr@5": sum(1 / r for r in ranks if r) / total,
    }


def print_table(results):
    print("| mode | language | queries | Recall@1 | Recall@3 | MRR@5 |")
    print("|---|---|---|---|---|---|")
    for mode, langs in results.items():
        for lang in ("en", "zh", "all"):
            if lang not in langs:
                continue
            m = langs[lang]
            print(
                f"| {mode} | {lang} | {m['queries']} | "
                f"{m['recall@1']:.2f} | {m['recall@3']:.2f} | {m['mrr@5']:.2f} |"
            )


def main():
    args = parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from src.config import Settings
    from src.rag import Provider, retrieve
    from src.store import Store

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    modules = (Settings, Store, Provider, retrieve)
    api_key = Settings().api_key

    modes = ["lexical", "hybrid"] if args.mode == "both" else [args.mode]
    results = {}
    for mode in modes:
        if mode == "hybrid" and not api_key:
            print("Skipping hybrid: set OPENAI_API_KEY (or .env) to run it.", file=sys.stderr)
            continue
        # Hybrid scores are continuous, so ties are rare and one run is enough
        # (and avoids re-embedding the dataset many times).
        runs = max(1, args.repeats) if mode == "lexical" else 1
        ranks = {}
        for _ in range(runs):
            for lang, found in evaluate(mode, dataset, modules, api_key).items():
                ranks.setdefault(lang, []).extend(found)
        ranks["all"] = [r for lang in list(ranks) for r in ranks[lang]]
        results[mode] = {lang: summarize(found, runs) for lang, found in ranks.items()}

    if not results:
        sys.exit("Nothing to run.")
    print_table(results)
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
