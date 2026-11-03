"""Tests for the demo shop: the cache, pool and config on their own, then the
full break -> fix flow of each scenario.

    ../Backend/.venv/bin/python -m unittest tests.test_shop -v
"""
import logging
import unittest

from fastapi.testclient import TestClient

import main
from cache import FakeRedis, RedisOOMError
from config import ConfigError, ServiceConfig
from db import FakeDBPool, PoolTimeoutError

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


class DBPoolTests(unittest.TestCase):
    def test_full_pool_times_out(self):
        p = FakeDBPool(size=2)
        p.acquire()
        p.acquire()
        with self.assertRaises(PoolTimeoutError) as e:
            p.acquire()
        for words in ("connection pool", "exhausted", "timeout waiting for a connection"):
            self.assertIn(words, str(e.exception))

    def test_release_leaked_makes_pool_work_again(self):
        p = FakeDBPool(size=5)
        p.leak(5)
        with self.assertRaises(PoolTimeoutError):
            p.acquire()
        p.release_leaked()
        p.acquire()
        self.assertEqual(p.info(), {"size": 5, "in_use": 1, "leaked": 0})

    def test_invalid_size_changes_nothing(self):
        p = FakeDBPool(size=10)
        with self.assertRaises(ValueError):
            p.config_set(size=0)
        self.assertEqual(p.size, 10)


class ConfigTests(unittest.TestCase):
    def test_v2_raises_config_error(self):
        c = ServiceConfig("v2")
        with self.assertRaises(ConfigError) as e:
            c.get_setting("payment_timeout_ms")
        for word in ("config", "typo", "release", "deploy"):
            self.assertIn(word, str(e.exception))

    def test_v1_reads_setting(self):
        self.assertEqual(ServiceConfig("v1").get_setting("payment_timeout_ms"), 3000)

    def test_unknown_release_rejected(self):
        c = ServiceConfig("v1")
        with self.assertRaises(ValueError):
            c.deploy("v3")
        self.assertEqual(c.current_release, "v1")


class ShopTests(unittest.TestCase):
    def setUp(self):
        # Fresh, healthy cache, pool and config for every test so tests don't affect each other.
        main.cache = FakeRedis(max_keys=100, policy="allkeys-lru")
        main.db = FakeDBPool(size=20)
        main.config = ServiceConfig("v1")
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

    def test_db_pool_break_and_fix(self):
        r = self.client.post("/admin/db/config", json={"size": 5, "leak": 5})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/checkout", json=ORDER)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"], "db_pool_exhausted")
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 503)
        self.assertEqual(health.json()["reason"], "database connection pool exhausted")

        r = self.client.post("/admin/db/config", json={"release_leaked": True, "size": 20})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/checkout", json=ORDER).status_code, 200)
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["db"], {"size": 20, "in_use": 0, "leaked": 0})

    def test_bad_config_break_and_rollback(self):
        r = self.client.post("/admin/deploy", json={"release": "v2"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/checkout", json=ORDER)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["error"], "config_error")
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 503)
        self.assertEqual(health.json()["reason"], "service config invalid after deploy of release v2")

        r = self.client.post("/admin/deploy", json={"release": "v1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.post("/checkout", json=ORDER).status_code, 200)
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["release"], "v1")

    def test_health_only_reads(self):
        self.client.post("/admin/db/config", json={"size": 5, "leak": 5})
        before = self.client.get("/health").json()
        self.client.get("/health")
        self.assertEqual(self.client.get("/health").json(), before)

    def test_invalid_db_config_and_release_rejected(self):
        self.assertEqual(self.client.post("/admin/db/config", json={"size": 0, "leak": 5}).status_code, 400)
        self.assertEqual(self.client.get("/health").json()["db"], {"size": 20, "in_use": 0, "leaked": 0})
        self.assertEqual(self.client.post("/admin/deploy", json={"release": "v3"}).status_code, 400)
        self.assertEqual(self.client.get("/health").json()["release"], "v1")


if __name__ == "__main__":
    unittest.main()
