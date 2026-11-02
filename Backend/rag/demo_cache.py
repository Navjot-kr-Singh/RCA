"""Demo mode: cached /analyze answers, so the API runs without an OpenAI key.

The cache holds one live answer per demo scenario. A query is answered with
the scenario whose words it shares most; learned incidents (LOCAL-...) that
BM25 finds for the query are put in front of the similar incidents, so the
learning loop still shows without a key.

Rebuild the cache (needs OPENAI_API_KEY, about 10 seconds per scenario):

    python -m rag.demo_cache
"""
import copy
import json

from .config import DEMO_CACHE_PATH
from .kb import tokenize
from .learn import ID_PREFIX

# The demo shop's scenarios, worded the way the triager hands them to the RCA agent.
SCENARIOS = [
    "demo-shop checkout returns HTTP 503 cache_unavailable: Redis OOM command not allowed "
    "when used memory > 'maxmemory'",
    "Checkout requests are slow and time out; database connection pool exhausted, "
    "timeout waiting for a connection from the pool",
    "Checkout fails right after a deploy; service config has a typo and the app "
    "cannot read its settings, errors started with the new release",
]


def load():
    return json.loads(DEMO_CACHE_PATH.read_text()) if DEMO_CACHE_PATH.exists() else []


def match(entries, text):
    """The cached entry sharing the most words with `text`, or None."""
    query = set(tokenize(text))
    best, best_score = None, 0.0
    for entry in entries:
        words = set(tokenize(entry["issue"]))
        score = len(query & words) / (len(words) or 1)
        if score > best_score:
            best, best_score = entry, score
    return best


def answer(kb, entries, text, learned_k=5):
    """A copy of the cached response for `text`, with matching learned incidents first."""
    entry = match(entries, text)
    if entry is None:
        return None
    result = copy.deepcopy(entry["response"])
    result["demo"] = {"matched_issue": entry["issue"]}
    learned = []
    for rank, (row, _) in enumerate(kb.bm25_search(text, learned_k), 1):
        d = kb.docs[row]
        if d["id"].startswith(ID_PREFIX):
            out = {k: d[k] for k in ("id", "org", "category", "severity", "issue", "root_cause",
                                     "solution", "source_url", "incident_date")}
            out["scores"] = {"bm25_rank": rank}
            learned.append(out)
    if learned:
        result["similar_incidents"] = learned + result["similar_incidents"]
    return result


def main():
    from .engine import Engine

    engine = Engine("full")
    entries = []
    for issue in SCENARIOS:
        response = engine.run(issue)
        response.pop("trace")
        entries.append({"issue": issue, "response": response})
        print(f"{response['mode']:5} {response['timing_s']['total']:5}s  {issue[:70]}")
    DEMO_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_CACHE_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=1))
    print(f"wrote {DEMO_CACHE_PATH}")


if __name__ == "__main__":
    main()
