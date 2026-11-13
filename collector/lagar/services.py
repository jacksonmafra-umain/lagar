"""Public services (Tjänster) from the curated list into the corpus.

`collector/data/services.json` is the source of truth for which services exist
and which corpus norms each one is based on (curated by hand, see
docs/specs/2026-11-13-tjanster-sources.md). For every entry the collector reads
the official `source` page and writes `corpus/services/service-<slug>.md`: the
curated fields as frontmatter and a body of a heading, the page's lead as
published (at most three sentences, never rewritten or translated) and a link
to the page.

The lead is the page's own introduction paragraph, found per host by its class
(`ingress`, `preamble`, `lead` ...); when the page has none, or it is a
navigation question ("Vad vill du veta mer om?"), the meta description is used,
unless the site cut it short with "...". Försäkringskassan's navigation pages put
a prompt for their link list in the ingress, so they use the meta description.

Every fetch is recorded in the committed manifest `sources/services-manifest.json`:
HTTP status, final URL, `Last-Modified`, the page's <title>, the SHA-256 of the
extracted title and lead (pages embed nonces and timestamps, so a hash of their
bytes would change on every run) and when it was fetched; an entry whose fields
did not change keeps its old `fetched_at`. Redirects are followed by hand and only within the page's own
host and robots.txt; a page that is gone (404, 410), redirects to another host,
is disallowed by robots.txt or answers 403 keeps the previous corpus file (or
writes nothing on a first run), is marked in the manifest and is reported. The
corpus file is only rewritten when its frontmatter or body change, so an
unchanged lead leaves it untouched; its `source_sha256` is the SHA-256 of the
lead, because the page bytes carry volatile parts.

robots.txt is read once per host (wildcards and `$` honoured) and its
`Crawl-delay` respected; requests are at least `--rate` seconds apart.
"""

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import frontmatter, htmlmd
from .caselaw import NETWORK_ERRORS, StateError, _load_state, _save_state
from .http import Blocked, PoliteClient
from .municipal import Robots
from .sfs import USER_AGENT
from .vocabulary import TYPES
from .writer import path_for, write

DEFAULT_LIST = "collector/data/services.json"
DEFAULT_STATE = "collector/data/services-state.json"
DEFAULT_MANIFEST = "sources/services-manifest.json"
MANIFEST_VERSION = 1
TYPE = "public_service"
MAX_SENTENCES = 3
MAX_REDIRECTS = 5
REDIRECTS = frozenset({301, 302, 303, 307, 308})
GONE = frozenset({404, 410})
REQUIRED = ("slug", "title", "issuer", "source", "audience", "topics", "scope", "based_on")

# Manifest results.
OK = "ok"
NOT_FOUND = "not_found"
REDIRECTED = "redirected"
ROBOTS = "robots"
BLOCKED = "blocked"
ERROR = "error"
NO_LEAD = "no_lead"

_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def _class_paragraph(name):
    """The first <p> whose class list holds `name`."""
    token = re.escape(name)
    return re.compile(rf'<p\b[^>]*\bclass="(?:[^"]*\s)?{token}(?:\s[^"]*)?"[^>]*>(.*?)</p>', re.S | re.I)


def _class_div(name):
    """The first <div> whose class is exactly `name` (a lead block of plain text)."""
    return re.compile(rf'<div\b[^>]*\bclass="{re.escape(name)}"[^>]*>(.*?)</div>', re.S | re.I)


# Where each host puts the lead of a page; hosts not listed use the meta description.
HOST_LEADS = {
    "www.forsakringskassan.se": (_class_paragraph("sv-font-ingress"),),
    "www.skatteverket.se": (_class_paragraph("ingress"),),
    "arbetsformedlingen.se": (_class_paragraph("ingress"),),
    "www.csn.se": (_class_paragraph("csn-formatmall-ingress"),),
    "www.migrationsverket.se": (_class_paragraph("mv-font-intro"),),
    "polisen.se": (_class_paragraph("preamble"),),
    "www.transportstyrelsen.se": (
        re.compile(r'<div\b[^>]*\bclass="lead"[^>]*>\s*(?:<div\b[^>]*>\s*)*<p\b[^>]*>(.*?)</p>', re.S | re.I),
    ),
    # Sources of the kommun and region template services.
    "www.boverket.se": (_class_paragraph("lead"),),
    "www.socialstyrelsen.se": (_class_div("preamble"),),
    "aldreguiden.se": (_class_div("preamble"),),
    "www.1177.se": (_class_paragraph("preamble"),),
    # A styled-components class: a fixed prefix and a generated suffix.
    "www.naturvardsverket.se": (
        re.compile(r'<p\b[^>]*\bclass="Typographystyles__Preamble-[^"]*"[^>]*>(.*?)</p>', re.S | re.I),
    ),
}
# On these hosts a page carrying the marker is a navigation page: its ingress is a prompt for the
# link list below it ("För att ge information om vad som gäller för dig behöver vi veta ..."), so
# the meta description is the lead.
NAVIGATION_PAGES = {
    "www.forsakringskassan.se": "navigationssida-innehall",
}
# Meta descriptions in order of preference (CSN's name="description" is the same on every page).
META_DESCRIPTIONS = ("og:description", "description")

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BREAK = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.S | re.I)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z][\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9\"”„«])")


class ListError(Exception):
    """The curated list is unreadable or invalid, or --slug names an unknown service."""


class NoLead(ValueError):
    """The page has no usable lead paragraph."""


# --- parsing ---------------------------------------------------------------


def _text(fragment):
    return htmlmd.clean_text(html.unescape(_TAG.sub("", _BREAK.sub(" ", _COMMENT.sub("", fragment or "")))))


def _metas(raw):
    """name or property -> content of the page's meta tags (the first one wins)."""
    out = {}
    for tag in _META.findall(raw):
        attrs = {m.group(1).lower(): m.group(2) if m.group(2) is not None else m.group(3) for m in _ATTR.finditer(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key and "content" in attrs:
            out.setdefault(key, _text(attrs["content"]))
    return out


def _usable(lead):
    """A lead is a statement: not empty, not a navigation question, not cut short by the site."""
    return bool(lead) and not lead.endswith(("?", "...", "…"))


def _first_sentences(text, count=MAX_SENTENCES):
    return " ".join(_SENTENCE_END.split(text)[:count])


@dataclass
class Page:
    title: "str | None"
    lead: str
    lead_source: str  # "ingress" (the page's lead paragraph) or "meta" (its meta description)


def extract(raw, url):
    """The page's <title> and lead; NoLead when neither a lead paragraph nor a meta description is usable."""
    host = urllib.parse.urlsplit(url).hostname
    title = _TITLE.search(raw)
    title = _text(title.group(1)) if title else None
    navigation = NAVIGATION_PAGES.get(host)
    patterns = () if navigation and navigation in raw else HOST_LEADS.get(host, ())
    for pattern in patterns:
        match = pattern.search(raw)
        lead = _text(match.group(1)) if match else ""
        if _usable(lead):
            return Page(title or None, _first_sentences(lead), "ingress")
    metas = _metas(raw)
    for key in META_DESCRIPTIONS:
        lead = metas.get(key, "")
        if _usable(lead):
            return Page(title or None, _first_sentences(lead), "meta")
    raise NoLead(f"no lead paragraph or meta description on {url}")


# --- curated list ----------------------------------------------------------


def load_list(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ListError(f"{path}: {error}") from None
    if not isinstance(data, list):
        raise ListError(f"{path}: expected a list of services")
    seen = set()
    for i, item in enumerate(data):
        where = f"{path}[{i}]"
        if not isinstance(item, dict):
            raise ListError(f"{where}: expected an object")
        missing = [k for k in REQUIRED if k not in item]
        if missing:
            raise ListError(f"{where}: missing {', '.join(missing)}")
        slug = item["slug"]
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
            raise ListError(f"{where}: slug {slug!r} is not lower-case ASCII words joined by '-'")
        if slug in seen:
            raise ListError(f"{where}: duplicate slug {slug!r}")
        seen.add(slug)
        source = urllib.parse.urlsplit(item["source"] if isinstance(item["source"], str) else "")
        if source.scheme != "https" or not source.hostname:
            raise ListError(f"{where}: source must be an https URL")
    return data


def select(entries, slugs=None, limit=None):
    if slugs:
        known = {e["slug"] for e in entries}
        unknown = [s for s in slugs if s not in known]
        if unknown:
            raise ListError(f"unknown slug: {', '.join(unknown)}")
        entries = [e for e in entries if e["slug"] in set(slugs)]
    return entries if limit is None else entries[:limit]


# --- documents -------------------------------------------------------------


def build_meta(entry, page, fetched_at):
    slug = entry["slug"]
    meta = {
        "id": "service-" + slug,
        "title": entry["title"],
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": slug,
        "issued": None,
        "in_force": None,
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": entry["source"],
        "source_sha256": hashlib.sha256(page.lead.encode("utf-8")).hexdigest(),
        "fetched_at": fetched_at,
        "issuer": entry["issuer"],
        "based_on": list(entry["based_on"]),
        "audience": list(entry["audience"]),
        "topics": list(entry["topics"]),
        "channels": list(entry.get("channels") or []),
        "service_url": entry.get("service_url"),
        "issuer_org_number": entry.get("issuer_org_number"),
        "scope": entry["scope"],
        "template": bool(entry.get("template", False)),
    }
    for key in ("region_code", "municipality_code"):
        if key in entry:
            meta[key] = entry[key]
    return meta


def to_markdown(entry, page):
    """A heading, the lead as published and a link to the official page."""
    return (f"# {entry['title']}\n\n{htmlmd.escape_block(page.lead)}\n\n"
            f"Källa: [{entry['issuer']}]({entry['source']})\n")


# --- fetching --------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Redirects come back as HTTPError, so the collector decides whether to follow them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def no_redirect_opener(request, timeout):
    return _OPENER.open(request, timeout=timeout)


def _same_site(url, origin):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname == urllib.parse.urlsplit(origin).hostname


class HostUnavailable(Exception):
    """robots.txt of a host could not be read; its pages are not fetched."""


@dataclass
class Fetched:
    result: str
    status: "int | None"
    final_url: str
    response: object = None
    error: "str | None" = None


class Site:
    """One host: its robots.txt rules and crawl delay, read once."""

    def __init__(self, client, origin, rate):
        self.client, self.origin, self.rate = client, origin, rate
        robots_url = origin + "/robots.txt"
        self.robots, self.crawl_delay = Robots(""), 0.0
        current = robots_url
        for _ in range(MAX_REDIRECTS + 1):
            client.min_interval = rate
            try:
                text = client.fetch_response(current).body.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as error:
                location = error.headers.get("Location") if error.headers else None
                error.close()
                if error.code in REDIRECTS and location:
                    current = urllib.parse.urljoin(current, location)
                    if not _same_site(current, origin):
                        raise HostUnavailable(f"{robots_url} redirects to another host: {current}") from None
                    continue
                if error.code in GONE:
                    return
                raise HostUnavailable(f"{robots_url}: HTTP {error.code}") from None
            except NETWORK_ERRORS as error:
                raise HostUnavailable(f"{robots_url}: {error}") from None
            self.robots = Robots(text)
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(text.splitlines())
            delay = parser.crawl_delay(USER_AGENT)
            self.crawl_delay = float(delay) if delay else 0.0
            return
        raise HostUnavailable(f"{robots_url}: too many redirects")

    def fetch(self, url):
        """Fetch `url`, following redirects only within this host and its robots.txt."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if not self.robots.allows(current):
                return Fetched(ROBOTS, None, current, error=f"robots.txt disallows {current}")
            self.client.min_interval = max(self.rate, self.crawl_delay)
            try:
                response = self.client.fetch_response(current)
            except urllib.error.HTTPError as error:
                location = error.headers.get("Location") if error.headers else None
                error.close()
                if error.code in REDIRECTS and location:
                    target = urllib.parse.urljoin(current, location)
                    if not _same_site(target, url):
                        return Fetched(REDIRECTED, error.code, target,
                                       error=f"HTTP {error.code} to another host: {target}")
                    current = target
                    continue
                if error.code in GONE:
                    return Fetched(NOT_FOUND, error.code, current, error=f"HTTP {error.code}")
                return Fetched(ERROR, error.code, current, error=f"HTTP {error.code}")
            return Fetched(OK, 200, current, response)
        return Fetched(ERROR, None, current, error="too many redirects")


# --- state and manifest ----------------------------------------------------


def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise StateError(f"manifest corrupt: {path}")
    return {e["slug"]: e for e in data["entries"]}


def save_manifest(path, entries):
    _save_state(path, {
        "version": MANIFEST_VERSION,
        "source": DEFAULT_LIST,
        "entries": [entries[slug] for slug in sorted(entries)],
    })


def content_sha256(page):
    """SHA-256 of what the corpus keeps from a page: its <title> and lead."""
    data = json.dumps([page.title, page.lead], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _record(entry, fetched, fetched_at, page=None):
    response = fetched.response
    record = {
        "slug": entry["slug"],
        "source": entry["source"],
        "result": fetched.result,
        "status": fetched.status,
        "final_url": fetched.final_url,
        "last_modified": response.headers.get("Last-Modified") if response is not None else None,
        "sha256": content_sha256(page) if page else None,
        "title": page.title if page else None,
        "lead_source": page.lead_source if page else None,
        "fetched_at": fetched_at,
    }
    if fetched.error:
        record["error"] = fetched.error
    return record


def _same_record(a, b):
    def strip(r):
        return {k: v for k, v in (r or {}).items() if k != "fetched_at"}
    return a is not None and strip(a) == strip(b)


# --- run -------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    moved: "list[dict]" = field(default_factory=list)
    failed: "list[dict]" = field(default_factory=list)
    blocked_hosts: "list[str]" = field(default_factory=list)


def _rate(value):
    rate = float(value)
    if rate < 1.0:
        raise argparse.ArgumentTypeError(f"must be at least 1 second: {value}")
    return rate


def _positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value}")
    return number


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py services")
    parser.add_argument("--slug", action="append", metavar="S", help="collect only this service (repeatable)")
    parser.add_argument("--limit", type=_positive, metavar="N", help="collect only the first N services")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=1.0, metavar="SECONDS")
    parser.add_argument("--list", default=DEFAULT_LIST)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    return parser.parse_args(argv)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _origin(url):
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _stored(meta, corpus):
    try:
        return frontmatter.load(path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None


def _store(entry, page, fetched_at, corpus):
    """Write the document unless the stored one has the same frontmatter (but fetched_at) and body."""
    meta = build_meta(entry, page, fetched_at)
    body = to_markdown(entry, page)
    stored, stored_body = _stored(meta, corpus)
    if stored is not None and stored_body == body and {k: v for k, v in stored.items() if k != "fetched_at"} == {
            k: v for k, v in meta.items() if k != "fetched_at"}:
        return False
    write(meta, body, corpus)
    return True


def _collect(site, entry, corpus):
    """(Fetched, Page or None, written) for one entry; never raises for a failed page."""
    fetched = site.fetch(entry["source"])
    if fetched.result != OK:
        return fetched, None, False
    try:
        page = extract(fetched.response.body.decode("utf-8"), fetched.final_url)
    except UnicodeDecodeError as error:
        fetched.result, fetched.error = ERROR, f"not UTF-8: {error}"
        return fetched, None, False
    except NoLead as error:
        fetched.result, fetched.error = NO_LEAD, str(error)
        return fetched, None, False
    return fetched, page, _store(entry, page, _now(), corpus)


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "moved": summary.moved,
        "failed": summary.failed,
        "blocked_hosts": summary.blocked_hosts,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    entries = select(load_list(args.list), args.slug, args.limit)
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    summary = RunSummary()
    sites = {}  # origin -> Site, or the reason the host is skipped
    blocked = {}  # origin -> message

    for entry in entries:
        slug, origin = entry["slug"], _origin(entry["source"])
        fetched, page, written = None, None, False
        try:
            if origin in blocked:
                fetched = Fetched(BLOCKED, None, entry["source"], error=blocked[origin])
            else:
                if origin not in sites:
                    try:
                        sites[origin] = Site(client, origin, args.rate)
                    except HostUnavailable as error:
                        sites[origin] = str(error)
                site = sites[origin]
                if isinstance(site, str):
                    fetched = Fetched(ERROR, None, entry["source"], error=site)
                else:
                    fetched, page, written = _collect(site, entry, args.corpus)
        except Blocked as error:
            blocked[origin] = str(error)
            summary.blocked_hosts.append(urllib.parse.urlsplit(origin).hostname)
            fetched = Fetched(BLOCKED, 403, entry["source"], error=str(error))
        except NETWORK_ERRORS as error:
            fetched = Fetched(ERROR, None, entry["source"], error=f"{type(error).__name__}: {error}")

        record = _record(entry, fetched, _now(), page)
        if _same_record(manifest.get(slug), record):
            record = manifest[slug]
        manifest[slug] = record
        state["done"][slug] = fetched.result
        if fetched.result == OK:
            state["failed"].pop(slug, None)
            (summary.written if written else summary.unchanged).append(slug)
            if fetched.final_url != entry["source"]:
                summary.moved.append({"slug": slug, "final_url": fetched.final_url})
        else:
            state["failed"][slug] = fetched.error or fetched.result
            summary.failed.append({"slug": slug, "result": fetched.result, "status": fetched.status,
                                   "final_url": fetched.final_url, "error": fetched.error})

    state["blocked"] = "; ".join(f"{o}: {m}" for o, m in sorted(blocked.items())) or None
    _save_state(args.state, state)
    save_manifest(args.manifest, manifest)
    if args.report:
        _write_report(args.report, summary)
    return summary


def main(argv, client=None):
    if argv and argv[0] == "services":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate, opener=no_redirect_opener)
    try:
        summary = run(client, args)
    except (ListError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{len(summary.moved)} moved, {len(summary.failed)} failed"
        + (f", BLOCKED by {', '.join(summary.blocked_hosts)}" if summary.blocked_hosts else ""),
        flush=True,
    )
    for failure in summary.failed:
        print(f"failed: {failure['slug']}: {failure['result']} ({failure['error']})", flush=True)
    for moved in summary.moved:
        print(f"moved: {moved['slug']} -> {moved['final_url']}", flush=True)
    return 2 if summary.blocked_hosts else 0
