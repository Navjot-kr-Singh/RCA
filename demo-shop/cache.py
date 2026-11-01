"""In-memory stand-in for Redis with a memory limit and an eviction policy.

Lets the demo hit a realistic Redis OOM error without running a real Redis.
"""

POLICIES = ("noeviction", "allkeys-lru")


class RedisOOMError(Exception):
    """Raised on a write when the cache is full and the policy is noeviction."""


class FakeRedis:
    def __init__(self, max_keys, policy):
        self._store = {}
        self.evicted_keys = 0
        self.config_set(max_keys=max_keys, policy=policy)

    def config_set(self, max_keys=None, policy=None):
        """Change the limit or the policy at runtime, like Redis's CONFIG SET."""
        # Validate everything first so a bad value never leaves a half-applied change.
        if max_keys is not None and max_keys < 1:
            raise ValueError("max_keys must be at least 1")
        if policy is not None and policy not in POLICIES:
            raise ValueError(f"policy must be one of {POLICIES}")
        if max_keys is not None:
            self.max_keys = max_keys
        if policy is not None:
            self.policy = policy

    def set(self, key, value):
        if key in self._store:
            # Overwriting needs no extra memory; re-inserted below as most recently used.
            self._store.pop(key)
        else:
            if len(self._store) >= self.max_keys and self.policy == "noeviction":
                raise RedisOOMError("OOM command not allowed when used memory > 'maxmemory'.")
            while len(self._store) >= self.max_keys:
                self._evict_lru()
        self._store[key] = value

    def get(self, key):
        if key not in self._store:
            return None
        # Move the key to the end so it counts as most recently used.
        value = self._store.pop(key)
        self._store[key] = value
        return value

    def info(self):
        used = len(self._store)
        return {
            "used_keys": used,
            "max_keys": self.max_keys,
            "policy": self.policy,
            "evicted_keys": self.evicted_keys,
            "usage_ratio": round(used / self.max_keys, 2),
        }

    def _evict_lru(self):
        # Dicts keep insertion order, so the first key is the least recently used.
        oldest = next(iter(self._store))
        del self._store[oldest]
        self.evicted_keys += 1
