import io
import unittest
import urllib.error
from email.message import Message

from lagar.http import Blocked, PoliteClient


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers

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


def closed(error):
    return error.fp.closed


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
        if isinstance(result, tuple):
            return FakeResponse(*result)
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

    def test_fetch_returns_body_and_bare_content_type(self):
        headers = Message()
        headers["Content-Type"] = "Application/PDF; charset=binary"
        client, _, _ = make([(b"%PDF", headers)])
        self.assertEqual(client.fetch("http://x/a.pdf"), (b"%PDF", "application/pdf"))

    def test_extra_headers_are_sent_with_the_user_agent(self):
        client, opener, _ = make([b"ok"])
        client.get("http://x", {"Accept": "text/html", "User-Agent": "spoof"})
        request = opener.requests[0]
        self.assertEqual(request.get_header("Accept"), "text/html")
        self.assertEqual(request.get_header("User-agent"), "lagar-test/1.0 (+https://example.org)")

    def test_fetch_final_returns_the_redirected_url(self):
        class Redirected(FakeResponse):
            def geturl(self):
                return "http://y/final"

        opener = lambda request, timeout=None: Redirected(b"body")  # noqa: E731
        client = PoliteClient("ua", opener=opener, clock=lambda: 0.0, sleep=lambda s: None)
        self.assertEqual(client.fetch_final("http://x"), (b"body", None, "http://y/final"))
        client, _, _ = make([b"plain"])
        self.assertEqual(client.fetch_final("http://x"), (b"plain", None, "http://x"))

    def test_fetch_without_content_type_header(self):
        client, _, _ = make([(b"x", Message())])
        self.assertEqual(client.fetch("http://x"), (b"x", None))

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

    def test_backoff_is_2_4_8_seconds(self):
        client, _, sleeps = make([http_error(503) for _ in range(3)] + [b"ok"], min_interval=0)
        self.assertEqual(client.get("http://x"), b"ok")
        self.assertEqual(sleeps, [2, 4, 8])

    def test_retries_500_502_504(self):
        for code in (500, 502, 504):
            with self.subTest(code=code):
                client, opener, sleeps = make([http_error(code), b"ok"], min_interval=0)
                self.assertEqual(client.get("http://x"), b"ok")
                self.assertEqual(sleeps, [2])
                self.assertEqual(len(opener.requests), 2)

    def test_retry_after_above_cap_raises_blocked(self):
        client, opener, sleeps = make([http_error(429, "3600")])
        with self.assertRaises(Blocked) as ctx:
            client.get("http://x")
        self.assertIn("Retry-After", str(ctx.exception))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(sleeps, [])

    def test_retry_after_at_cap_is_honoured(self):
        client, _, sleeps = make([http_error(429, "300"), b"ok"], min_interval=0)
        self.assertEqual(client.get("http://x"), b"ok")
        self.assertEqual(sleeps, [300])

    def test_error_responses_closed_on_retry_and_blocked_paths(self):
        retried = http_error(503)
        client, _, _ = make([retried, b"ok"])
        client.get("http://x")
        self.assertTrue(closed(retried))
        forbidden = http_error(403)
        client, _, _ = make([forbidden])
        with self.assertRaises(Blocked):
            client.get("http://x")
        self.assertTrue(closed(forbidden))
        too_long = http_error(429, "9999")
        client, _, _ = make([too_long])
        with self.assertRaises(Blocked):
            client.get("http://x")
        self.assertTrue(closed(too_long))


if __name__ == "__main__":
    unittest.main()
