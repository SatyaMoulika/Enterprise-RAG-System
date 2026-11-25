"""Evaluate source files through application services, never through prewritten chunks."""

import hashlib
import json
import time
from io import BytesIO
from types import SimpleNamespace

from models.enterprise import Enterprise
from models.user import User
from schemas.document import DocumentAccess
from services.chat_service import ChatService
from services.document_service import DocumentService
from services.generation_protocol import PROMPT_VERSION


def evaluate_sources(data, root, db):
    workspace = Enterprise(name="Isolated source evaluation")
    db.add(workspace)
    db.flush()
    people = {name for q in data["queries"] if (name := q.get("employee"))}
    people.update(d["recipient"] for d in data["documents"] if d.get("recipient"))
    users = {}
    for number, name in enumerate(sorted(people)):
        user = User(
            name=name,
            email=f"reviewer-{number}@example.invalid",
            enterprise_id=workspace.id,
            role="employee",
            is_active=True,
            hashed_password="unusable-evaluation-account",
        )
        db.add(user)
        db.flush()
        users[name] = user
    db.commit()
    documents = {}
    ingestion = []
    for row in data["documents"]:
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Evaluation source must be inside the dataset directory")
        raw = path.read_bytes()
        access = DocumentAccess(
            visibility=row.get("visibility", "company"),
            recipient_ids=[users[row["recipient"]].id] if row.get("recipient") else [],
        )
        start = time.perf_counter()
        document = DocumentService.upload_document(
            db, workspace.id, SimpleNamespace(filename=path.name, file=BytesIO(raw)), access
        )
        documents[row["key"]] = document.id
        ingestion.append(
            {
                "key": row["key"],
                "document_id": document.id,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "seconds": time.perf_counter() - start,
                "index_metadata": document.index_metadata,
                "warnings": document.extraction_warnings,
            }
        )
    results = []
    for query in data["queries"]:
        start = time.perf_counter()
        try:
            trace = {}
            answer = ChatService.ask(
                query["question"],
                workspace.id,
                db,
                user=users.get(query.get("employee")),
                review_trace=trace,
            )
            expected = {documents[key] for key in query["relevant_documents"]}
            found = set(answer["sources"])
            results.append(
                {
                    "id": query["id"],
                    "profile": "application",
                    "question": query["question"],
                    "reference_answer": query["reference_answer"],
                    "relevant_ids": sorted(expected),
                    "status": "ok" if answer["citations"] else "no_context",
                    **answer,
                    "generation_trace": trace,
                    "document_recall": len(found & expected) / len(expected) if expected else None,
                    "review": {"correct": None, "refused": None, "claims": []},
                    "elapsed_seconds": time.perf_counter() - start,
                }
            )
        except Exception:
            db.rollback()
            results.append(
                {
                    "id": query["id"],
                    "profile": "application",
                    "question": query["question"],
                    "reference_answer": query["reference_answer"],
                    "relevant_ids": [documents[key] for key in query["relevant_documents"]],
                    "status": "pipeline_error",
                    "elapsed_seconds": time.perf_counter() - start,
                }
            )
    return {
        "dataset_description": data.get("description"),
        "dataset_sha256": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
        "prompt_version": PROMPT_VERSION,
        "ingestion": ingestion,
        "results": results,
        "caveat": "Application-service regression on development fixtures. Correctness and claim support require explicit review. Timings include application ingestion/retrieval/generation, excluding network UI overhead.",
    }
