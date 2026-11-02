from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from rag import demo_cache, learn
from rag.config import DEMO_MODE
from rag.engine import Engine
from rag.present import summary_markdown

app = FastAPI(title="Root Cause Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loads the prebuilt index from index/full; run `python -m rag.build_index` first.
engine = Engine("full")
learned_count = learn.load_into(engine.kb)
demo_entries = demo_cache.load() if DEMO_MODE else []


class Query(BaseModel):
    issue: str
    rerank: Optional[bool] = None  # None = RCA_RERANK default (off for local models)
    debug: bool = False


class Incident(BaseModel):
    issue: str
    root_cause: str
    solution: str
    category: str = "other"
    severity: str = "High"
    org: Optional[str] = None
    source_url: Optional[str] = None
    incident_date: Optional[str] = None


@app.get("/")
def home():
    return {
        "message": "RCA API is running 🚀",
        "incidents_indexed": len(engine.kb.docs),
        "learned_incidents": learned_count,
        "demo_mode": DEMO_MODE,
    }


def add_legacy_fields(result):
    """Also fill the fields the React frontend (Frontend/src/parse.js) reads:
    analysis.{root_causes, solutions, confidence, explanation} and
    similar_issues[{content, similarity_score}]. The new fields stay alongside."""
    a = result["analysis"]
    a["root_causes"] = [h["cause"] for h in a["hypotheses"]]
    a["solutions"] = a["fix_steps"]
    a["confidence"] = a["hypotheses"][0]["likelihood"] if a["hypotheses"] else a["category_confidence"]
    a["explanation"] = " ".join(
        [a["summary"], f"Category: {a['category']}, severity: {a['severity']}."]
        + [h["reasoning"] for h in a["hypotheses"][:1]]
    )
    result["similar_issues"] = [
        {
            "content": f"Issue: {s['issue']}\nCauses: {s['root_cause']}\nSolutions: {s['solution']}",
            "similarity_score": s["scores"].get("relevance", 0) / 10 if "relevance" in s["scores"]
            else s["scores"].get("cosine", 0),
            "id": s["id"],
            "org": s["org"],
            "source_url": s["source_url"],
        }
        for s in result["similar_incidents"]
    ] if result["mode"] == "RAG" else []
    if result["mode"] == "NOVEL":
        result["mode"] = "LLM_ONLY"
    return result


@app.post("/analyze")
def analyze(query: Query):
    if DEMO_MODE:
        result = demo_cache.answer(engine.kb, demo_entries, query.issue)
        if result is None:
            raise HTTPException(404, "Demo mode has no cached answer for this issue. Cached issues: "
                                + " | ".join(e["issue"] for e in demo_entries))
    else:
        result = engine.run(query.issue, rerank=query.rerank)
        if not query.debug:
            result.pop("trace")
    result = add_legacy_fields(result)
    result["summary_markdown"] = summary_markdown(result)
    return result


@app.post("/incidents")
def add_incident(incident: Incident):
    """Learning loop: index a resolved incident so later analyses can cite it."""
    global learned_count
    try:
        doc, embedded = learn.add(engine.kb, incident.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    learned_count += 1
    return {"id": doc["id"], "embedded": embedded, "incidents_indexed": len(engine.kb.docs)}
