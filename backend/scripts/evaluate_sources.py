"""Run the real pipeline against source files in a new disposable SQLite database."""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evaluation/sources/cases.json",
    )
    parser.add_argument("--allow-inference", action="store_true")
    parser.add_argument("--case-ids", help="Comma-separated source case IDs")
    args = parser.parse_args()
    if not args.allow_inference:
        parser.error("This runs your configured models. Select --allow-inference to continue")
    # Set before any application imports. A real development DB is never touched.
    with TemporaryDirectory(prefix="rag-source-review-") as directory:
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(directory) / "review.db")
        os.environ["UPLOAD_DIR"] = str(Path(directory) / "uploads")
        os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from core.config import settings
        from database.base import Base
        from database.session import SessionLocal, engine
        from evaluation.sources import evaluate_sources
        from models.document_chunk import DocumentChunk  # noqa: F401

        Base.metadata.create_all(engine)
        data = json.loads(args.dataset.read_text())
        if args.case_ids:
            selected = set(args.case_ids.split(","))
            if not selected <= {row["id"] for row in data["queries"]}:
                parser.error("Unknown source case ID")
            data["queries"] = [row for row in data["queries"] if row["id"] in selected]
        with SessionLocal() as db:
            report = evaluate_sources(data, args.dataset.parent, db)
        report["runtime"] = {
            name: getattr(settings, name)
            for name in (
                "RETRIEVAL_STRATEGY",
                "RETRIEVAL_TOP_K",
                "RETRIEVAL_CANDIDATES",
                "RETRIEVAL_MIN_SIMILARITY",
                "RETRIEVAL_NEIGHBORS",
                "RETRIEVAL_CONTEXT_CHARACTERS",
                "RERANKER_MODE",
                "RERANKER_MODEL",
                "EMBEDDING_BACKEND",
                "EMBEDDING_MODEL",
                "EMBEDDING_REVISION",
                "OLLAMA_CHAT_MODEL",
                "FINANCIAL_CALCULATIONS_ENABLED",
                "GENERATION_CONTEXT_TOKENS",
                "GENERATION_MAX_TOKENS",
                "GENERATION_TEMPERATURE",
            )
        }
        engine.dispose()
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
