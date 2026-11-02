"""Tests for the demo shop: the cache on its own, then the full break -> fix flow.

    .venv/bin/python -m unittest tests.test_shop -v
"""
import logging
import unittest

from fastapi.testclient import TestClient

import main
from cache import FakeRedis, RedisOOMError

# Hide the shop's request logs so the test results are easy to read.
logging.disable(logging.CRITICAL)

ORDER = {"user_id": "u1", "items": ["tshirt"]}


class CacheTests(unittest.TestCase):
    def test_noeviction_raises_oom_when_full(self):
        c = FakeRedis(max_keys=1, policy="noeviction")
        c.set("a", 1)
        with self.assertRaises(RedisOOMError):
            c.set("b", 2)

    def test_lru_evicts_least_recently_used(self):
        c = FakeRedis(max_keys=2, policy="allkeys-lru")
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")
        c.set("c", 3)
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("a"), 1)

    def test_bad_config_changes_nothing(self):
        c = FakeRedis(max_keys=10, policy="allkeys-lru")
        with self.assertRaises(ValueError):
            c.config_set(max_keys=5, policy="lru")
        self.assertEqual(c.max_keys, 10)


class ShopTests(unittest.TestCase):
    def setUp(self):
        # Fresh, healthy cache for every test so tests don't affect each other.
        main.cache = FakeRedis(max_keys=100, policy="allkeys-lru")
        self.client = TestClient(main.app)

    def break_cache(self):
        r = self.client.post("/admin/cache/config", json={"max_keys": 3, "policy": "noeviction"})
        self.assertEqual(r.status_code, 200)

    def test_health_ok(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_checkout_ok(self):
        r = self.client.post("/checkout", json=ORDER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "confirmed")

    def test_empty_items_rejected(self):
        r = self.client.post("/checkout", json={"user_id": "u1", "items": []})
        self.assertEqual(r.status_code, 422)

    def test_break_makes_checkout_fail_with_oom(self):
        self.break_cache()
        codes = [self.client.post("/checkout", json=ORDER).status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 503])
        self.assertEqual(self.client.get("/health").status_code, 503)

    def test_fix_restores_checkout(self):
        self.break_cache()
        for _ in range(4):
            self.client.post("/checkout", json=ORDER)
        r = self.client.post("/admin/cache/config", json={"max_keys": 100, "policy": "allkeys-lru"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/checkout", json=ORDER).status_code, 200)
        self.assertEqual(self.client.get("/health").json()["status"], "ok")

    def test_invalid_config_rejected(self):
        r = self.client.post("/admin/cache/config", json={"max_keys": 5, "policy": "lru"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get("/health").json()["cache"]["max_keys"], 100)


if __name__ == "__main__":
    unittest.main()
