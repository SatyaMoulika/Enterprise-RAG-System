"""Durable database queue; isolate each parse/index job in a bounded subprocess."""

import argparse
import os
import resource
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402

from database.session import SessionLocal  # noqa: E402
from models.document import Document  # noqa: E402
from models.document_chunk import DocumentChunk  # noqa: F401, E402
from models.enterprise import Enterprise  # noqa: F401, E402
from models.user import User  # noqa: F401, E402
from services.document_service import DocumentService  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="Drain currently queued jobs, then exit"
    )
    parser.add_argument("--job", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--recover-stale-minutes",
        type=int,
        help="Mark interrupted jobs failed so an administrator can retry them",
    )
    args = parser.parse_args()
    timeout = int(os.environ.get("INGESTION_TIMEOUT_SECONDS", "900"))
    if args.job:
        memory = int(os.environ.get("INGESTION_MEMORY_MB", "4096")) * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        with SessionLocal() as db:
            DocumentService.process_next(db, args.job)
        return
    if args.recover_stale_minutes is not None:
        if args.recover_stale_minutes * 60 <= timeout:
            parser.error("Stale recovery must exceed INGESTION_TIMEOUT_SECONDS")
        cutoff = datetime.now(UTC) - timedelta(minutes=args.recover_stale_minutes)
        with SessionLocal() as db:
            db.execute(
                update(Document)
                .where(Document.index_status == "indexing", Document.index_started_at < cutoff)
                .values(
                    index_status="failed",
                    index_started_at=None,
                    index_error="Indexing was interrupted. Retry indexing.",
                )
            )
            db.commit()

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    while True:
        with SessionLocal() as db:
            identity = db.scalar(
                select(Document.id)
                .where(Document.index_status == "queued")
                .order_by(Document.id)
                .limit(1)
            )
        if identity is None:
            if args.once:
                return
            time.sleep(2)
            continue
        try:
            completed = subprocess.run(
                [sys.executable, __file__, "--job", str(identity)], timeout=timeout, check=False
            )
            failed = completed.returncode != 0
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            failed = True
            if isinstance(exc, KeyboardInterrupt):
                with SessionLocal() as db:
                    db.execute(
                        update(Document)
                        .where(Document.id == identity, Document.index_status == "indexing")
                        .values(
                            index_status="failed",
                            index_started_at=None,
                            index_error="Indexing was interrupted. Retry indexing.",
                        )
                    )
                    db.commit()
                return
        if failed:
            with SessionLocal() as db:
                db.execute(
                    update(Document)
                    .where(Document.id == identity, Document.index_status == "indexing")
                    .values(
                        index_status="failed",
                        index_started_at=None,
                        index_error="Indexing exceeded worker limits or exited unexpectedly. Retry indexing.",
                    )
                )
                db.commit()


if __name__ == "__main__":
    main()
