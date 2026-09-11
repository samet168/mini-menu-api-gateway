import asyncio
from collections import defaultdict, deque
import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    """
    Thread-safe, sliding-window in-memory rate limiter per client IP address.
    """

    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, client_ip: str) -> Tuple[bool, int, int]:
        """
        Records an access for client_ip.
        Returns:
            is_allowed (bool)
            remaining_requests (int)
            reset_seconds (int)
        """
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            timestamps = self._history[client_ip]

            # Evict timestamps outside current sliding window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            current_count = len(timestamps)
            if current_count >= self.max_requests:
                earliest_request = timestamps[0]
                reset_seconds = max(1, int(self.window_seconds - (now - earliest_request)))
                return False, 0, reset_seconds

            timestamps.append(now)
            remaining = max(0, self.max_requests - (current_count + 1))
            return True, remaining, self.window_seconds


rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
    window_seconds=60,
)


async def enforce_rate_limit(request: Request) -> None:
    """
    FastAPI dependency / middleware check that applies rate limiting per client IP.
    """
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "127.0.0.1")
    )

    allowed, remaining, reset_in = await rate_limiter.check_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_REQUESTS_PER_MINUTE} requests per minute. Retry in {reset_in} seconds.",
            headers={"Retry-After": str(reset_in), "X-RateLimit-Remaining": "0"},
        )
