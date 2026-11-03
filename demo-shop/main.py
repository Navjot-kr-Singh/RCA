"""Sandbox demo shop: a tiny checkout service backed by a fake Redis, a fake
database connection pool and a per-release service config.

Run from this folder:
    ../Backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
"""
import logging
import os
import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cache import FakeRedis, RedisOOMError
from config import ConfigError, ServiceConfig
from db import FakeDBPool, PoolTimeoutError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("demo-shop")

app = FastAPI(title="Demo Shop (sandbox)")
cache = FakeRedis(
    max_keys=int(os.getenv("CACHE_MAX_KEYS", "100")),
    policy=os.getenv("CACHE_POLICY", "allkeys-lru"),
)
db = FakeDBPool(size=int(os.getenv("DB_POOL_SIZE", "20")))
config = ServiceConfig(release=os.getenv("SHOP_RELEASE", "v1"))


class CheckoutRequest(BaseModel):
    user_id: str
    items: list[str] = Field(min_length=1)


class CacheConfig(BaseModel):
    max_keys: Optional[int] = None
    policy: Optional[str] = None


class DBConfig(BaseModel):
    size: Optional[int] = None
    leak: Optional[int] = None
    release_leaked: bool = False


class Deploy(BaseModel):
    release: str


def cache_rejects_writes():
    info = cache.info()
    return info["policy"] == "noeviction" and info["used_keys"] >= info["max_keys"]


@app.get("/health")
def health():
    """Reads state only; the Fixer runs it before and after a fix."""
    body = {"cache": cache.info(), "db": db.info(), "release": config.current_release, "config_ok": config.ok()}
    reason = None
    if not body["config_ok"]:
        reason = f"service config invalid after deploy of release {config.current_release}"
    elif db.exhausted():
        reason = "database connection pool exhausted"
    elif cache_rejects_writes():
        reason = "cache full and policy is noeviction"
    if reason:
        return JSONResponse(status_code=503, content={"status": "degraded", "reason": reason, **body})
    return {"status": "ok", **body}


@app.post("/checkout")
def checkout(req: CheckoutRequest):
    order_id = uuid.uuid4().hex[:8]
    try:
        config.get_setting("payment_timeout_ms")
    except ConfigError as e:
        log.error("checkout failed user=%s: %s", req.user_id, e)
        return JSONResponse(status_code=500, content={"error": "config_error", "detail": str(e)})
    try:
        db.acquire()
    except PoolTimeoutError as e:
        log.error("checkout failed user=%s: %s", req.user_id, e)
        return JSONResponse(status_code=503, content={"error": "db_pool_exhausted", "detail": str(e)})
    try:
        # The order is "saved" while the connection is held.
        cache.set(f"checkout:{order_id}", {"user_id": req.user_id, "items": req.items})
    except RedisOOMError as e:
        log.error("checkout failed user=%s: %s", req.user_id, e)
        return JSONResponse(status_code=503, content={"error": "cache_unavailable", "detail": str(e)})
    finally:
        db.release()
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


@app.post("/admin/db/config")
def set_db_config(cfg: DBConfig):
    """Sandbox-only: resize the pool, leak connections or release the leaked ones; used by break.sh and fix.sh."""
    # Validate everything first so a bad value never leaves a half-applied change.
    if cfg.size is not None and cfg.size < 1:
        return JSONResponse(status_code=400, content={"error": "invalid_config", "detail": "size must be at least 1"})
    if cfg.leak is not None and cfg.leak < 1:
        return JSONResponse(status_code=400, content={"error": "invalid_config", "detail": "leak must be at least 1"})
    if cfg.release_leaked:
        db.release_leaked()
    db.config_set(size=cfg.size)
    if cfg.leak is not None:
        db.leak(cfg.leak)
    log.warning("db pool changed: size=%s leaked=%s", db.size, db.leaked)
    return {"status": "updated", "db": db.info()}


@app.post("/admin/deploy")
def deploy(req: Deploy):
    """Sandbox-only stand-in for a deploy or rollback; used by break.sh and fix.sh."""
    try:
        config.deploy(req.release)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": "invalid_release", "detail": str(e)})
    log.warning("deployed release %s", config.current_release)
    return {"status": "deployed", "release": config.current_release, "config_ok": config.ok()}
