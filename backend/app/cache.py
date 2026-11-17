"""Tiny key-value cache: Redis when REDIS_URL is set, in-process dict otherwise (dev/tests)."""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.config import get_settings


class _Memory:
    def __init__(self):
        self._d: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, k):
        with self._lock:
            v = self._d.get(k)
            if not v:
                return None
            if v[0] and v[0] < time.time():
                self._d.pop(k, None)
                return None
            return v[1]

    def set(self, k, v, ex=None):
        with self._lock:
            self._d[k] = ((time.time() + ex) if ex else 0, v)

    def delete(self, k):
        with self._lock:
            self._d.pop(k, None)

    def incr(self, k):
        with self._lock:
            exp, v = self._d.get(k, (0, "0"))
            n = int(v) + 1
            self._d[k] = (exp, str(n))
            return n

    def expire(self, k, s):
        with self._lock:
            if k in self._d:
                self._d[k] = (time.time() + s, self._d[k][1])

    def flushall(self):
        with self._lock:
            self._d.clear()


_client = None


def client():
    global _client
    if _client is None:
        url = get_settings().redis_url
        if url:
            import redis

            _client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        else:
            _client = _Memory()
    return _client


def get_json(key: str) -> Any:
    try:
        v = client().get(key)
        return json.loads(v) if v else None
    except Exception:
        return None


def set_json(key: str, value: Any, ttl: int = 600) -> None:
    try:
        client().set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass
