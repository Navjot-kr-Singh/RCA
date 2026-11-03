"""In-memory stand-in for a database connection pool that can leak connections.

Lets the demo hit a realistic pool exhaustion error without running a real database.
"""


class PoolTimeoutError(Exception):
    """Raised by acquire() when every connection in the pool is in use."""


class FakeDBPool:
    def __init__(self, size):
        self.in_use = 0
        self.leaked = 0
        self.config_set(size=size)

    def config_set(self, size=None):
        """Change the pool size at runtime, like a pool's max-connections setting."""
        # Validate everything first so a bad value never leaves a half-applied change.
        if size is not None and size < 1:
            raise ValueError("size must be at least 1")
        if size is not None:
            self.size = size

    def acquire(self):
        # A real pool would wait for a free connection; failing at once keeps the demo and tests fast.
        if self.in_use + self.leaked >= self.size:
            # Worded with "connection pool exhausted" so the RCA demo mode matches this scenario.
            raise PoolTimeoutError(
                f"database connection pool exhausted: timeout waiting for a connection from the pool "
                f"(pool size {self.size}, all {self.size} in use)"
            )
        self.in_use += 1

    def release(self):
        if self.in_use > 0:
            self.in_use -= 1

    def leak(self, n):
        """Take n connections that are never released, like code that forgets to close them."""
        if n < 1:
            raise ValueError("leak must be at least 1")
        self.leaked += n

    def release_leaked(self):
        """Return the leaked connections to the pool."""
        self.leaked = 0

    def info(self):
        return {"size": self.size, "in_use": self.in_use + self.leaked, "leaked": self.leaked}

    def exhausted(self):
        return self.in_use + self.leaked >= self.size
