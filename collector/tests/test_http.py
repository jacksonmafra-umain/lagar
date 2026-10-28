import io
import unittest
import urllib.error
from email.message import Message

from lagar.http import Blocked, PoliteClient


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, retry_after=None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", code, "err", headers, io.BytesIO(b""))


class FakeOpener:
    def __init__(self, results):
        self.results = list(results)
        self.requests = []
        self.timeouts = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        self.timeouts.append(timeout)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


def make(results, **kwargs):
    sleeps = []
    opener = FakeOpener(results)
    client = PoliteClient(
        "lagar-test/1.0 (+https://example.org)",
        opener=opener,
        clock=lambda: 0.0,
        sleep=sleeps.append,
        **kwargs,
    )
    return client, opener, sleeps


class PoliteClientTest(unittest.TestCase):
    def test_sends_user_agent(self):
        client, opener, _ = make([b"ok"])
        self.assertEqual(client.get("http://x/a"), b"ok")
        self.assertEqual(
            opener.requests[0].get_header("User-agent"),
            "lagar-test/1.0 (+https://example.org)",
        )
        self.assertEqual(opener.timeouts[0], 30)

    def test_spaces_requests_by_min_interval(self):
        client, _, sleeps = make([b"a", b"b"])
        client.get("http://x/1")
        self.assertEqual(sleeps, [])
        client.get("http://x/2")
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 1.0)

    def test_retries_429_using_retry_after(self):
        client, _, sleeps = make([http_error(429, "5"), b"body"])
        self.assertEqual(client.get("http://x"), b"body")
        self.assertIn(5, sleeps)

    def test_gives_up_after_max_retries(self):
        client, opener, _ = make([http_error(503) for _ in range(4)])
        with self.assertRaises(urllib.error.HTTPError):
            client.get("http://x")
        self.assertEqual(len(opener.requests), 4)

    def test_403_raises_blocked_without_retry(self):
        client, opener, _ = make([http_error(403)])
        with self.assertRaises(Blocked):
            client.get("http://x")
        self.assertEqual(len(opener.requests), 1)

    def test_404_reraised_immediately(self):
        client, opener, _ = make([http_error(404)])
        with self.assertRaises(urllib.error.HTTPError):
            client.get("http://x")
        self.assertEqual(len(opener.requests), 1)


if __name__ == "__main__":
    unittest.main()
