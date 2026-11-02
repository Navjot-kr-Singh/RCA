"""Sandbox demo shop: a tiny checkout service backed by a fake Redis.

Run from this folder:
    .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
"""
import logging
import os
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cache import FakeRedis, RedisOOMError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("demo-shop")

app = FastAPI(title="Demo Shop (sandbox)")
cache = FakeRedis(
    max_keys=int(os.getenv("CACHE_MAX_KEYS", "100")),
    policy=os.getenv("CACHE_POLICY", "allkeys-lru"),
)


class CheckoutRequest(BaseModel):
    user_id: str
    items: list[str] = Field(min_length=1)


class CacheConfig(BaseModel):
    max_keys: Optional[int] = None
    policy: Optional[str] = None


def cache_rejects_writes():
    info = cache.info()
    return info["policy"] == "noeviction" and info["used_keys"] >= info["max_keys"]


@app.get("/health")
def health():
    info = cache.info()
    if cache_rejects_writes():
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "reason": "cache full and policy is noeviction", "cache": info},
        )
    return {"status": "ok", "cache": info}


@app.post("/checkout")
def checkout(req: CheckoutRequest):
    order_id = uuid.uuid4().hex[:8]
    try:
        cache.set(f"checkout:{order_id}", {"user_id": req.user_id, "items": req.items})
    except RedisOOMError as e:
        log.error("checkout failed user=%s: %s", req.user_id, e)
        return JSONResponse(status_code=503, content={"error": "cache_unavailable", "detail": str(e)})
    log.info("checkout ok order=%s user=%s items=%d", order_id, req.user_id, len(req.items))
    return {"order_id": order_id, "status": "confirmed"}


@app.post("/admin/cache/config")
def set_cache_config(cfg: CacheConfig):
    """Sandbox-only stand-in for `redis-cli CONFIG SET`; used by break.sh and fix.sh."""
    try:
        cache.config_set(max_keys=cfg.max_keys, policy=cfg.policy)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "invalid_config", "detail": str(e)})
    log.warning("cache config changed: max_keys=%s policy=%s", cache.max_keys, cache.policy)
    return {"status": "updated", "cache": cache.info()}
