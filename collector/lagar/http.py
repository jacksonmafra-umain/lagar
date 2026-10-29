"""Polite HTTP client: spaced requests, honest User-Agent, bounded retries."""

import time
import urllib.error
import urllib.request

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
TIMEOUT_SECONDS = 30
MAX_RETRY_AFTER_SECONDS = 300


def _content_type(response):
    headers = getattr(response, "headers", None)
    value = headers.get("Content-Type") if headers is not None else None
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _final_url(response, url):
    geturl = getattr(response, "geturl", None)
    return (geturl() if callable(geturl) else None) or url


class Blocked(Exception):
    """The source refused access or asked for a long pause; collection must stop."""


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

    def get(self, url, headers=None):
        return self.fetch(url, headers)[0]

    def fetch(self, url, headers=None):
        """Return (body, content_type); content_type is lower-case, without parameters."""
        return self.fetch_final(url, headers)[:2]

    def fetch_final(self, url, headers=None):
        """Return (body, content_type, final_url): the URL answered after any redirects.

        `headers` are sent in addition to the User-Agent (for example Accept).
        """
        attempt = 0
        while True:
            self._space()
            request = urllib.request.Request(
                url, headers={**(headers or {}), "User-Agent": self.user_agent}
            )
            try:
                with self._opener(request, timeout=TIMEOUT_SECONDS) as response:
                    return response.read(), _content_type(response), _final_url(response, url)
            except urllib.error.HTTPError as error:
                if error.code == 403:
                    error.close()
                    raise Blocked(f"403 Forbidden: {url}") from error
                if error.code not in RETRY_STATUSES or attempt >= self.max_retries:
                    raise
                backoff = 2 ** (attempt + 1)
                retry_after = self._retry_after(error)
                error.close()
                if retry_after is not None and retry_after > MAX_RETRY_AFTER_SECONDS:
                    raise Blocked(
                        f"Retry-After {retry_after}s exceeds the "
                        f"{MAX_RETRY_AFTER_SECONDS}s cap: {url}"
                    ) from error
                self._sleep(retry_after if retry_after is not None else backoff)
                attempt += 1
