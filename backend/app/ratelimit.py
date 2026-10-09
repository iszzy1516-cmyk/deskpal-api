"""Fixed-window rate limiter.

In-memory dict of counters keyed by (bucket, key). Good for a single-process
deployment and for tests; swap the store for Redis when running multiple
workers (REDIS_URL is already in settings for exactly that upgrade).

Enforced limits live in app/main.py as dependencies on the routes.
"""
import threading
import time


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: dict[tuple[str, str], list[float]] = {}

    def check(self, bucket: str, key: str, max_hits: int, window_seconds: int) -> bool:
        """True if allowed, False if the limit is exceeded."""
        now = time.monotonic()
        k = (bucket, key)
        with self._lock:
            hits = [t for t in self._hits.get(k, []) if now - t < window_seconds]
            if len(hits) >= max_hits:
                self._hits[k] = hits
                return False
            hits.append(now)
            self._hits[k] = hits
            return True


limiter = RateLimiter()


def client_ip(request) -> str:
    """Best-effort client IP. Behind a trusted proxy you'd read X-Forwarded-For."""
    if request.client:
        return request.client.host
    return "unknown"
