"""EU case law in Swedish from the Publications Office Cellar into the corpus.

The collection is bounded: judgments of the Court of Justice (CELEX type CJ)
and the General Court (TJ) that Cellar records as interpreting one of the
curated EU acts (`collector/data/eu-acts.json`). One SPARQL query lists them,
one query per judgment reads its metadata, and Cellar content negotiation
(`/resource/celex/<CELEX>` with `Accept-Language: swe`) returns the Swedish
text, converted with the EU act converter. Only publications.europa.eu (and
op.europa.eu, where its robots.txt lives) is contacted; eur-lex.europa.eu is
refused, including as a redirect target.

Judgments without a Swedish expression, or with Swedish only as PDF or print,
are recorded as coverage gaps; nothing is ever translated. Only the language of
the case is authentic, so a Swedish text is `authoritative` only in a case
conducted in Swedish.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import frontmatter, writer
from .caselaw import personal_numbers
from .eu import (
    BASE,
    CELEX_URL,
    DEFAULT_LIST,
    DEFAULT_RATE,
    FORMATS,
    SPARQL_HEADERS,
    SPARQL_URL,
    ForbiddenHost,
    Gap,
    ListingError,
    _before,
    _Cache,
    _https,
    _rate,
    _robots_allows,
    _since,
    _utc,
    cellar_opener,
    check_host,
    derived_number,
    load_list,
    to_markdown,
)
from .http import Blocked, PoliteClient
from .sfs import NETWORK_ERRORS, USER_AGENT, StateError, _save_state
from .vocabulary import TYPES

DEFAULT_STATE = "collector/data/eu-case-law-state.json"
DEFAULT_MANIFEST = "sources/eu-case-law-manifest.json"
MANIFEST_VERSION = 1
TYPE = "eu_judgment"

DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError, KeyError, TypeError, ForbiddenHost)

# Judgments of the Court of Justice (CJ) and the General Court (TJ).
CASE_CELEX = re.compile(r"6\d{4}(CJ|TJ)\d{4}", re.ASCII)
_ACT_CELEX = re.compile(r"3\d{4}[RLD]\d{4}", re.ASCII)
_ECLI = re.compile(r"ECLI:[A-Z]{2}:[A-Z0-9.]{1,7}:\d{4}:[A-Za-z0-9.]{1,25}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
SWEDISH = "http://publications.europa.eu/resource/authority/language/SWE"
ISSUERS = {"CJ": "Europeiska unionens domstol", "TJ": "Europeiska unionens tribunal"}

_SWEDISH_EXPRESSION = f"""?expr cdm:expression_belongs_to_work ?work ;
            cdm:expression_uses_language <{SWEDISH}>"""

_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?field ?value WHERE {
  ?work cdm:resource_legal_id_celex "%(celex)s"^^xsd:string .
  { ?work cdm:work_date_document ?value BIND("date_document" AS ?field) }
  UNION { ?work cdm:case-law_ecli ?value BIND("ecli" AS ?field) }
  UNION { ?work cdm:case-law_uses_procedure_language ?value BIND("procedure_language" AS ?field) }
  UNION { ?work cdm:case-law_joins_case_court ?value BIND("joined" AS ?field) }
  UNION { ?work cdm:case-law_interpretes_resource_legal ?act .
          ?act cdm:resource_legal_id_celex ?value BIND("interprets" AS ?field) }
  UNION { %(expression)s ;
            cdm:expression_title ?value BIND("title_sv" AS ?field) }
  UNION { %(expression)s .
          ?manifestation cdm:manifestation_manifests_expression ?expr ;
            cdm:manifestation_type ?value BIND("manifestation_sv" AS ?field) }
}
"""

# Judgments interpreting one of the acts, with their newest Cellar modification.
# %(values)s are CELEX literals of the acts; %(since)s is an optional filter.
_LIST_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX cmr: <http://publications.europa.eu/ontology/cdm/cmr#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex (MAX(?m) AS ?modified) WHERE {
  VALUES ?act_celex { %(values)s }
  ?act cdm:resource_legal_id_celex ?act_celex .
  ?work cdm:case-law_interpretes_resource_legal ?act ;
        cdm:resource_legal_id_celex ?celex ;
        cmr:lastModificationDate ?m .
  FILTER(REGEX(STR(?celex), "^6[0-9]{4}(CJ|TJ)[0-9]{4}$"))
  %(since)s
} GROUP BY ?celex
"""


# --- metadata -----------------------------------------------------------------


@dataclass
class Metadata:
    celex: str
    fields: "dict[str, list[str]]"

    def all(self, name):
        return self.fields.get(name, [])

    def first(self, name):
        values = sorted(self.all(name))
        return values[0] if values else None

    @property
    def title_parts(self):
        """The Swedish title's `#`-separated parts: court and date, parties, procedure, keywords."""
        title = self.first("title_sv") or ""
        return [" ".join(p.split()) for p in title.split("#") if p.strip()]

    @property
    def manifestations(self):
        return set(self.all("manifestation_sv"))

    @property
    def joined(self):
        """CELEX numbers of the cases joined with this one, from `.../case/celex%3A<CELEX>` URIs."""
        out = set()
        for value in self.all("joined"):
            celex = urllib.parse.unquote(value).rsplit(":", 1)[-1]
            if CASE_CELEX.fullmatch(celex) and celex != self.celex:
                out.add(celex)
        return sorted(out)

    @property
    def interprets(self):
        return sorted({c for c in self.all("interprets") if _ACT_CELEX.fullmatch(c)})


def metadata_url(celex):
    if not CASE_CELEX.fullmatch(celex):
        raise ValueError(f"not a CELEX number of a judgment: {celex!r}")
    query = _QUERY % {"celex": celex, "expression": _SWEDISH_EXPRESSION}
    return SPARQL_URL + "?" + urllib.parse.urlencode({"query": query})


def parse_metadata(celex, raw):
    data = json.loads(raw.decode("utf-8"))
    fields = {}
    for row in data["results"]["bindings"]:
        name, value = row["field"]["value"], row["value"]["value"]
        values = fields.setdefault(name, [])
        if value not in values:
            values.append(value)
    if not fields:
        raise ValueError(f"{celex} is not in Cellar")
    return Metadata(celex, fields)


def list_url(acts, since=None):
    """SPARQL for the judgments interpreting `acts`, optionally only those changed after `since`."""
    for celex in acts:
        if not _ACT_CELEX.fullmatch(celex):
            raise ValueError(f"not a CELEX number of an act: {celex!r}")
    values = " ".join(f'"{c}"^^xsd:string' for c in acts)
    since_filter = f'FILTER(?m > "{_utc(since)}"^^xsd:dateTime)' if since else ""
    query = _LIST_QUERY % {"values": values, "since": since_filter}
    return SPARQL_URL + "?" + urllib.parse.urlencode({"query": query})


def parse_list(raw):
    """CELEX -> newest modification (UTC) from a list_url answer."""
    data = json.loads(raw.decode("utf-8"))
    out = {}
    for row in data["results"]["bindings"]:
        celex, latest = row["celex"]["value"], _utc(row["modified"]["value"])
        if CASE_CELEX.fullmatch(celex) and latest > out.get(celex, ""):
            out[celex] = latest
    return out


# --- frontmatter --------------------------------------------------------------


def case_number(celex):
    """`62012CJ0293` -> `C-293/12`, `62019TJ0012` -> `T-12/19`; Court of Justice cases before 1989 have no prefix."""
    year, kind, ordinal = int(celex[1:5]), celex[5:7], int(celex[7:11])
    prefix = "T-" if kind == "TJ" else "C-" if year >= 1989 else ""
    return f"{prefix}{ordinal}/{year % 100:02d}"


def corpus_id(celex):
    return "eu-" + celex.lower()


def _date(value):
    value = (value or "")[:10]
    return value if _ISO_DATE.fullmatch(value) else None


def title(metadata):
    """Court, date and parties: `Domstolens dom (stora avdelningen) av den 8 april 2014. Digital Rights Ireland Ltd mot ...`."""
    parts = metadata.title_parts
    return " ".join(parts[:2]) if parts else None


def build_meta(metadata, raw_sha256, source, fetched_at):
    celex = metadata.celex
    kind = celex[5:7]
    ecli = metadata.first("ecli") or ""
    return {
        "id": corpus_id(celex),
        "title": title(metadata),
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": case_number(celex),
        "issued": _date(metadata.first("date_document")),
        "in_force": None,
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        # Only the language of the case is authentic.
        "authoritative": metadata.all("procedure_language") == [SWEDISH],
        "source": source,
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
        "issuer": ISSUERS[kind],
        "court": kind,
        "ecli": ecli if _ECLI.fullmatch(ecli) else None,
        "celex": celex,
    }


def to_body(meta, metadata, raw):
    """The converted judgment, with the joined cases and the interpreted acts listed under the title."""
    text = to_markdown(meta["title"], raw)
    heading, _, rest = text.partition("\n\n")
    lines = [f"Mål: {', '.join([meta['number']] + [case_number(c) for c in metadata.joined])}"]
    if meta["ecli"]:
        lines.append(f"ECLI: {meta['ecli']}")
    if metadata.interprets:
        lines.append(f"Tolkar: {', '.join(derived_number(c) for c in metadata.interprets)}")
    return heading + "\n\n" + "  \n".join(lines) + "\n\n" + rest


# --- run ----------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    skipped: int = 0
    gaps: "list[str]" = field(default_factory=list)
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False
    latest_modified: "str | None" = None
    retry_from: "str | None" = None


def _case_arg(value):
    items = [v.strip().upper() for v in value.split(",") if v.strip()]
    for item in items:
        if not CASE_CELEX.fullmatch(item):
            raise argparse.ArgumentTypeError(f"not a CELEX number of a judgment (CJ or TJ): {item}")
    return items


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py eu-case-law")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--celex", type=_case_arg, action="extend", metavar="CELEX[,CELEX...]",
                        help="judgments to collect, such as 62012CJ0293")
    source.add_argument("--list", metavar="FILE",
                        help=f"collect the judgments interpreting the acts of a list file, e.g. {DEFAULT_LIST}")
    parser.add_argument("--refresh", action="store_true", help="refetch judgments already collected")
    parser.add_argument("--changed-since", type=_since, metavar="DATE[TIME]",
                        help="with --list, only judgments that Cellar changed after this moment (UTC)")
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents")
    parser.add_argument("--cache", metavar="DIR", help="keep the fetched bytes in DIR")
    parser.add_argument("--offline", action="store_true",
                        help="read metadata and text from --cache instead of the network")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=DEFAULT_RATE, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    if args.offline and not args.cache:
        parser.error("--offline needs --cache")
    if args.changed_since and not args.list:
        parser.error("--changed-since needs --list")
    if args.offline and args.list:
        parser.error("--offline needs --celex: listing the judgments asks Cellar")
    return args


def _load_state(path):
    state = {"done": {}, "failed": {}, "gaps": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    if not isinstance(loaded, dict) or not all(
        isinstance(loaded.get(k, {}), dict) for k in ("done", "failed", "gaps")
    ):
        raise StateError(f"state file corrupt: {path}")
    for key in state:
        if key in loaded:
            state[key] = loaded[key]
    return state


def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": MANIFEST_VERSION, "source": BASE, "judgments": [], "gaps": []}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("judgments"), list):
        raise StateError(f"manifest corrupt: {path}")
    data.setdefault("gaps", [])
    return data


def save_manifest(path, manifest):
    manifest["judgments"].sort(key=lambda e: e["celex"])
    manifest["gaps"].sort(key=lambda e: e["celex"])
    _save_state(path, manifest)


def _record_judgment(manifest, entry):
    manifest["gaps"] = [g for g in manifest["gaps"] if g["celex"] != entry["celex"]]
    old = next((e for e in manifest["judgments"] if e["celex"] == entry["celex"]), None)
    if old is not None and old.get("sha256") == entry["sha256"] and old.get("url") == entry["url"]:
        return  # same bytes: keep the first retrieval date
    manifest["judgments"] = [e for e in manifest["judgments"] if e["celex"] != entry["celex"]]
    manifest["judgments"].append(entry)


def _record_gap(manifest, celex, reason):
    manifest["gaps"] = [g for g in manifest["gaps"] if g["celex"] != celex]
    manifest["gaps"].append({"celex": celex, "reason": reason})


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_metadata(client, celex, cache):
    name = f"{celex}.sparql.json"
    if cache.offline:
        raw = cache.read(name)
    else:
        raw = client.get(check_host(metadata_url(celex)), SPARQL_HEADERS)
        cache.write(name, raw)
    return parse_metadata(celex, raw)


def _text_format(metadata):
    if not metadata.title_parts:
        raise Gap("no Swedish expression")
    for name in FORMATS:
        if name in metadata.manifestations:
            return name
    found = ", ".join(sorted(metadata.manifestations)) or "none"
    raise Gap(f"no Swedish XHTML or HTML manifestation (found: {found})")


def _fetch_text(client, celex, fmt, cache):
    accept, expected = FORMATS[fmt]
    if cache.offline:
        raw = cache.read(f"{celex}.{fmt}")
        source = json.loads(cache.read(f"{celex}.source.json").decode("utf-8"))
        content_type, final = source["content_type"], source["url"]
    else:
        url = check_host(CELEX_URL.format(celex=celex))
        raw, content_type, final = client.fetch_final(url, {"Accept": accept, "Accept-Language": "swe"})
    final = _https(final)
    check_host(final)
    if content_type not in expected:
        raise ValueError(f"expected {fmt}, got {content_type}")
    cache.write(f"{celex}.{fmt}", raw)
    cache.write(f"{celex}.source.json", json.dumps({"url": final, "content_type": content_type}).encode())
    return raw, content_type, final


def _stored(meta, corpus):
    try:
        return frontmatter.load(writer.path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None


def _done(state, celex, corpus):
    return celex in state["done"] and writer.path_for({"id": corpus_id(celex), "type": TYPE}, corpus).exists()


def _store(client, celex, args, manifest, cache):
    """Fetch, convert and write one judgment; returns (sha256, corpus changed)."""
    metadata = fetch_metadata(client, celex, cache)
    fmt = _text_format(metadata)
    raw, content_type, source = _fetch_text(client, celex, fmt, cache)
    sha = hashlib.sha256(raw).hexdigest()
    meta = build_meta(metadata, sha, source, _now())
    stored, stored_body = _stored(meta, args.corpus)
    if cache.offline and stored:  # nothing was fetched: keep the stored retrieval time
        meta["fetched_at"] = stored.get("fetched_at") or meta["fetched_at"]
    body = to_body(meta, metadata, raw)
    found = personal_numbers(body)
    if found:
        raise ValueError(f"possible personal identity number in the text ({len(found)} found)")
    _record_judgment(manifest, {
        "celex": celex,
        "id": meta["id"],
        "url": source,
        "content_type": content_type,
        "bytes": len(raw),
        "sha256": sha,
        "retrieved_at": meta["fetched_at"],
    })
    if stored is not None:
        stored = {k: v for k, v in stored.items() if k != "fetched_at"}
        if stored_body == body and stored == {k: v for k, v in meta.items() if k != "fetched_at"}:
            return sha, False
    writer.write(meta, body, args.corpus)
    return sha, True


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "gaps": summary.gaps,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "latest_modified": summary.latest_modified,
        "retry_from": summary.retry_from,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    state["blocked"] = None

    def finish():
        _save_state(args.state, state)
        save_manifest(args.manifest, manifest)
        if args.report:
            _write_report(args.report, summary)
        return summary

    def finish_blocked(message):
        summary.blocked = True
        state["blocked"] = message
        return finish()

    cache = _Cache(args.cache, args.offline)
    modified = {}  # --list: CELEX -> newest modification
    try:
        if not args.offline and not _robots_allows(client):
            return finish_blocked("robots.txt disallows the Cellar SPARQL or resource paths")
        if args.list:
            acts = list(dict.fromkeys(load_list(args.list)))
            raw = client.get(check_host(list_url(acts, args.changed_since)), SPARQL_HEADERS)
            modified = parse_list(raw)
            candidates = sorted(modified)
            summary.latest_modified = max(modified.values(), default=None)
        else:
            candidates = list(dict.fromkeys(args.celex))
    except Blocked as error:
        return finish_blocked(str(error))
    except DOCUMENT_ERRORS as error:
        finish()
        raise ListingError(f"judgment listing: {type(error).__name__}: {error}") from error
    refresh = args.refresh or bool(args.changed_since)
    pending = []

    try:
        for celex in candidates:
            if args.limit is not None and len(summary.written) >= args.limit:
                pending.append(celex)
                continue
            if not refresh and _done(state, celex, args.corpus):
                summary.skipped += 1
                continue
            try:
                sha, written = _store(client, celex, args, manifest, cache)
            except Gap as gap:
                summary.gaps.append(celex)
                state["gaps"][celex] = str(gap)
                state["failed"].pop(celex, None)
                _record_gap(manifest, celex, str(gap))
                continue
            except DOCUMENT_ERRORS as error:
                summary.failed.append(celex)
                pending.append(celex)
                state["failed"][celex] = f"{type(error).__name__}: {error}"
                continue
            (summary.written if written else summary.unchanged).append(celex)
            state["done"][celex] = sha
            state["failed"].pop(celex, None)
            state["gaps"].pop(celex, None)
            _save_state(args.state, state)
    except Blocked as error:
        done = set(summary.written) | set(summary.unchanged) | set(summary.gaps)
        pending = [c for c in candidates if c not in done]
        if modified and pending:
            summary.retry_from = _before(min(modified[c] for c in pending))
        return finish_blocked(str(error))
    if modified and pending:
        summary.retry_from = _before(min(modified[c] for c in pending))
    return finish()


def main(argv, client=None):
    if argv and argv[0] == "eu-case-law":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate, opener=cellar_opener())
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{summary.skipped} skipped, {len(summary.gaps)} gaps, {len(summary.failed)} failed"
        + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.gaps:
        print("gaps: " + ", ".join(summary.gaps), flush=True)
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
