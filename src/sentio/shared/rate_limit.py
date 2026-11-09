"""Token-bucket rate limiter used by the API rate-limit middleware."""

import time


class RateLimiter:
    """
    Simple token-bucket rate limiter.
    Used to throttle webcam processing or API calls.

    Args:
        rate : Maximum calls per second
        burst: Maximum burst size (default = rate)

    Usage:
        limiter = RateLimiter(rate=10)    # max 10 calls/sec
        if limiter.allow():
            process_frame()
    """

    def __init__(self, rate, burst=None):
        self.rate = float(rate)
        self.burst = float(burst or rate)
        self._tokens = self.burst
        self._last = time.perf_counter()

    def allow(self):
        """
        Returns True if a call is allowed under the rate limit.
        Refills tokens based on elapsed time.
        """
        now = time.perf_counter()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_and_allow(self):
        """Block until a token is available, then consume it."""
        while not self.allow():
            time.sleep(1.0 / self.rate)

    def retry_after(self):
        import math

        return max(1, math.ceil((1 - self._tokens) / self.rate))
