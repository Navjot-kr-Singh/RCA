"""Learning loop: incidents resolved in the incident room join the index.

Each one is stored in data/learned_incidents.json with an id like LOCAL-0001
and its embedding, and is re-added to the knowledge base at startup, so the
next similar alert can cite it.
"""
import json
import threading

import numpy as np

from .build_index import PAYLOAD_FIELDS
from .config import CATEGORIES, DEMO_MODE, LEARNED_PATH, SEVERITIES
from .llm import embed

ID_PREFIX = "LOCAL-"
DEFAULT_ORG = "OnCall Room"

_lock = threading.Lock()


def _load():
    return json.loads(LEARNED_PATH.read_text()) if LEARNED_PATH.exists() else []


def _save(entries):
    LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEARNED_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=1))


def _vector(kb, entry):
    """The stored embedding, a fresh one, or zeros in demo mode (BM25 only)."""
    if entry.get("vector"):
        return np.asarray(entry["vector"], dtype="float32"), False
    if DEMO_MODE:
        return np.zeros(kb.index.d, dtype="float32"), False
    return embed([entry["doc"]["issue"]])[0], True


def make_doc(fields, incident_id):
    """Validate the posted fields and return an index document."""
    for key in ("issue", "root_cause", "solution"):
        if not (fields.get(key) or "").strip():
            raise ValueError(f"{key} must not be empty")
    if fields.get("category", "other") not in CATEGORIES:
        raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
    if fields.get("severity", "High") not in SEVERITIES:
        raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")
    doc = {field: None for field in PAYLOAD_FIELDS}
    doc.update({
        "id": incident_id,
        "issue": fields["issue"].strip(),
        "root_cause": fields["root_cause"].strip(),
        "solution": fields["solution"].strip(),
        "category": fields.get("category") or "other",
        "severity": fields.get("severity") or "High",
        "org": fields.get("org") or DEFAULT_ORG,
        "source_url": fields.get("source_url"),
        "incident_date": fields.get("incident_date"),
        "provenance": "incident_room",
        "cause_is_vague": False,
    })
    return doc


def load_into(kb):
    """Add every stored incident to `kb`; embed and save any stored without a vector."""
    with _lock:
        entries = _load()
        changed = False
        for entry in entries:
            if entry["doc"]["id"] in kb.by_id:
                continue
            vector, fresh = _vector(kb, entry)
            if fresh:
                entry["vector"] = vector.tolist()
                changed = True
            kb.add(entry["doc"], vector)
        if changed:
            _save(entries)
        return len(entries)


def add(kb, fields):
    """Store a resolved incident and index it now. Returns (doc, embedded)."""
    with _lock:
        entries = _load()
        doc = make_doc(fields, f"{ID_PREFIX}{len(entries) + 1:04d}")
        entry = {"doc": doc, "vector": None}
        vector, embedded = _vector(kb, entry)
        if embedded:
            entry["vector"] = vector.tolist()
        kb.add(doc, vector)
        entries.append(entry)
        _save(entries)
        return doc, embedded
