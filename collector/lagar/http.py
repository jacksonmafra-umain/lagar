"""Polite HTTP client: spaced requests, honest User-Agent, bounded retries."""

import time
import urllib.error
import urllib.request

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
TIMEOUT_SECONDS = 30


class Blocked(Exception):
    """The source refused access (HTTP 403); collection must stop."""


class PoliteClient:
    def __init__(
        self,
        user_agent,
        min_interval=1.0,
        max_retries=3,
        opener=urllib.request.urlopen,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._opener = opener
        self._clock = clock
        self._sleep = sleep
        self._last_start = None

    def _space(self):
        if self._last_start is not None:
            wait = self.min_interval - (self._clock() - self._last_start)
            if wait > 0:
                self._sleep(wait)
        self._last_start = self._clock()

    @staticmethod
    def _retry_after(error):
        value = error.headers.get("Retry-After") if error.headers else None
        if value is None:
            return None
        try:
            seconds = int(str(value).strip())
        except ValueError:
            return None
        return seconds if seconds >= 0 else None

    def get(self, url):
        attempt = 0
        while True:
            self._space()
            request = urllib.request.Request(
                url, headers={"User-Agent": self.user_agent}
            )
            try:
                with self._opener(request, timeout=TIMEOUT_SECONDS) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                if error.code == 403:
                    raise Blocked(f"403 Forbidden: {url}") from error
                if error.code not in RETRY_STATUSES or attempt >= self.max_retries:
                    raise
                backoff = 2 ** (attempt + 1)
                retry_after = self._retry_after(error)
                self._sleep(retry_after if retry_after is not None else backoff)
                attempt += 1
