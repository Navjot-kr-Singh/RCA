"""Offline tests for the incident-room additions: demo mode, summary_markdown
and the learning loop (no API calls).

    python -m unittest tests.test_oncall -v
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from rag import demo_cache, learn
from rag.kb import KnowledgeBase
from rag.present import NOVEL_NOTE, summary_markdown


def sample_result(mode="RAG"):
    return {
        "mode": mode,
        "analysis": {
            "summary": "Checkout returns 503 because the cache rejects writes.",
            "category": "memory_leak",
            "severity": "High",
            "hypotheses": [
                {"cause": "Cache full with noeviction", "likelihood": 0.8,
                 "evidence_ids": ["GOLD-1486", "GOLD-0011"], "reasoning": "r"},
                {"cause": "Recent config change", "likelihood": 0.15, "evidence_ids": [], "reasoning": "r"},
            ],
            "first_checks": ["Check cache memory usage", "Check recent deploys"],
        },
        "similar_incidents": [
            {"id": "GOLD-1486", "org": "Sdf", "source_url": "https://status.sdf.cloud/x"},
        ],
    }


class SummaryMarkdownTests(unittest.TestCase):
    def test_rag_answer_lists_evidence_closest_incident_and_checks(self):
        md = summary_markdown(sample_result())
        self.assertIn("**RCA (RAG)** · category `memory_leak` · severity **High**", md)
        self.assertIn("1. Cache full with noeviction (80%, evidence: GOLD-1486, GOLD-0011)", md)
        self.assertIn("2. Recent config change (15%, evidence: no past incident)", md)
        self.assertIn("**Closest past incident:** GOLD-1486 (Sdf) <https://status.sdf.cloud/x>", md)
        self.assertIn("2. Check recent deploys", md)
        self.assertNotIn(NOVEL_NOTE, md)

    def test_llm_only_answer_says_so_and_names_no_past_incident(self):
        md = summary_markdown(sample_result("LLM_ONLY"))
        self.assertIn(NOVEL_NOTE, md)
        self.assertNotIn("Closest past incident", md)

    def test_demo_answer_is_labelled(self):
        result = sample_result()
        result["demo"] = {"matched_issue": "Redis OOM"}
        self.assertIn('_Demo mode: cached answer for "Redis OOM"._', summary_markdown(result))


class DemoCacheTests(unittest.TestCase):
    entries = [{"issue": s, "response": {"n": i}} for i, s in enumerate(demo_cache.SCENARIOS)]

    def test_each_scenario_matches_its_own_wording(self):
        self.assertEqual(demo_cache.match(self.entries, "Redis OOM on checkout, maxmemory reached")["response"]["n"], 0)
        self.assertEqual(demo_cache.match(self.entries, "connection pool exhausted, checkout slow")["response"]["n"], 1)
        self.assertEqual(demo_cache.match(self.entries, "config typo after the new deploy")["response"]["n"], 2)

    def test_unrelated_text_matches_nothing(self):
        self.assertIsNone(demo_cache.match(self.entries, "zzz qqq"))


class LearningLoopTests(unittest.TestCase):
    fields = {
        "issue": "demo-shop checkout returns 503 cache_unavailable after the cache filled up",
        "root_cause": "Cache limit of 3 keys with the noeviction policy rejected new writes.",
        "solution": "Switched the eviction policy to allkeys-lru and raised the limit to 100 keys.",
        "category": "database_issue",
        "severity": "Critical",
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "learned.json"
        patches = [mock.patch.object(learn, "LEARNED_PATH", path),
                   mock.patch.object(learn, "DEMO_MODE", True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_rejects_bad_fields(self):
        with self.assertRaises(ValueError):
            learn.make_doc({**self.fields, "root_cause": " "}, "LOCAL-0001")
        with self.assertRaises(ValueError):
            learn.make_doc({**self.fields, "category": "redis"}, "LOCAL-0001")
        with self.assertRaises(ValueError):
            learn.make_doc({**self.fields, "severity": "Sev1"}, "LOCAL-0001")

    def test_added_incident_is_found_and_survives_a_restart(self):
        kb = KnowledgeBase("train")
        before = len(kb.docs)
        doc, embedded = learn.add(kb, self.fields)
        self.assertEqual(doc["id"], "LOCAL-0001")
        self.assertFalse(embedded)
        self.assertEqual(len(kb.docs), before + 1)
        self.assertEqual(kb.index.ntotal, len(kb.docs))
        top_row = kb.bm25_search("checkout 503 cache_unavailable noeviction", 1)[0][0]
        self.assertEqual(kb.docs[top_row]["id"], "LOCAL-0001")

        restarted = KnowledgeBase("train")
        self.assertEqual(learn.load_into(restarted), 1)
        self.assertIn("LOCAL-0001", restarted.by_id)
        self.assertEqual(learn.add(restarted, self.fields)[0]["id"], "LOCAL-0002")

    def test_demo_answer_puts_learned_incident_first(self):
        kb = KnowledgeBase("train")
        learn.add(kb, self.fields)
        entries = [{"issue": demo_cache.SCENARIOS[0],
                    "response": {"mode": "RAG", "similar_incidents": [{"id": "GOLD-1486"}]}}]
        result = demo_cache.answer(kb, entries, "checkout 503 cache_unavailable Redis OOM noeviction")
        self.assertEqual([s["id"] for s in result["similar_incidents"]], ["LOCAL-0001", "GOLD-1486"])
        self.assertEqual(entries[0]["response"]["similar_incidents"], [{"id": "GOLD-1486"}])

    def test_zero_vector_keeps_dense_search_working(self):
        kb = KnowledgeBase("train")
        learn.add(kb, self.fields)
        hits = kb.dense_search(np.ones(kb.index.d, dtype="float32") / np.sqrt(kb.index.d), 3)
        self.assertEqual(len(hits), 3)


if __name__ == "__main__":
    unittest.main()
