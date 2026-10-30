"""Processing log of Swedish legal sources: AGENCIES.md and its JSON report.

The list of agency regulation series (författningssamlingar) and other legal
sources comes from lagrummet.se's `rattskalla` index, which links every source
to its official page and describes it; the court list comes from the rättspraxis
API. Both are fetched only with `--refresh` (robots.txt checked, one request
each, collector User-Agent) and cached in `collector/data/rattskalla.json` and
`collector/data/courts.json`, so the report is rebuilt offline. Agency names,
statuses, reasons for gaps and tracking issues are curated in
`collector/data/agencies.json`; document counts come from the corpus, county
and kommun configuration from `counties.json` and `municipalities.json`, kommun
websites from `kommuner.json`, the kommun list from the app's bundled geo file.
"""

import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from . import progress
from .agency import ListingError, _Robots
from .caselaw import NETWORK_ERRORS, USER_AGENT
from .http import Blocked, PoliteClient

INDEX_HOST = "https://www.lagrummet.se"
INDEX_URL = INDEX_HOST + "/rattskalla/"
COURTS_HOST = "https://rattspraxis.etjanst.domstol.se"
COURTS_URL = COURTS_HOST + "/api/v1/domstolar"
COURT_SEARCH = COURTS_HOST + "/sok/sokning?filter="
ISSUES_URL = "https://github.com/jacksonmafra-umain/lagar/issues/"
DEFAULT_CACHE = "collector/data/rattskalla.json"
DEFAULT_COURTS = "collector/data/courts.json"
DEFAULT_KOMMUNER = "collector/data/kommuner.json"
DEFAULT_LANDING = "landing/data/sources.json"
DEFAULT_CURATED = "collector/data/agencies.json"
DEFAULT_REPORT = "collector/data/agencies-report.json"
DEFAULT_COUNTIES = "collector/data/counties.json"
DEFAULT_MUNICIPALITIES = "collector/data/municipalities.json"
DEFAULT_MUNICIPAL_MANIFEST = "sources/municipal-manifest.json"
DEFAULT_GEO = "app/shared/src/commonMain/composeResources/files/geo/sweden.json"
MIN_RATE = 1.0

STATUSES = {
    "collected": "collected",
    "collected_pdf": "collected: metadata and PDF links (text only in PDF, not extracted yet)",
    "partial": "partly collected",
    "blocked": "not collected: blocked by a WAF",
    "api_key": "not collected: API key needed",
    "robots": "not collected: robots.txt disallows",
    "no_adapter": "not collected: no adapter yet",
    "no_number": "not collected: no report number in the API",
    "out_of_scope": "out of scope",
    "unclassified": "unclassified: new or unknown lagrummet.se entry",
}
_ORDER = list(STATUSES)
_COUNTY_SLUG = re.compile(r"^.+-lans-forfattningssamling-(\d{2})-?fs$")
_YEAR = re.compile(r"(\d{4}):\d+")
_ARTICLE = re.compile(r"<article\b(.*?)</article>", re.S)
_HREF = re.compile(r'<a\b[^>]*\bhref="([^"]+)"')
_TITLE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
_DESCRIPTION = re.compile(r'<div class="text-sm[^"]*">(.*?)</div>', re.S)
_TAG = re.compile(r"<[^>]+>")


def _text(fragment):
    return " ".join(html.unescape(_TAG.sub("", fragment)).split())


def slugify(title):
    """`Arbetsmiljöverkets författningssamling (AFS)` -> `arbetsmiljoverkets-forfattningssamling-afs`."""
    ascii_title = unicodedata.normalize("NFKD", title.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")


def parse_index(raw):
    """[{slug, title, url, description}] for every entry on the rättskällor index, sorted by slug.

    The page lists every entry at once (its pagination is client-side); `url` is
    the official page the entry links to, `description` lagrummet.se's Swedish
    summary of the source or None.
    """
    pages = []
    for block in _ARTICLE.findall(raw.decode("utf-8") if isinstance(raw, bytes) else raw):
        href, title = _HREF.search(block), _TITLE.search(block)
        if not (href and title):
            continue
        description = _DESCRIPTION.search(block)
        name = _text(title.group(1))
        pages.append({"slug": slugify(name), "title": name, "url": html.unescape(href.group(1)).strip(),
                      "description": _text(description.group(1)) or None if description else None})
    return sorted(pages, key=lambda p: (p["slug"], p["url"]))


def parse_courts(raw):
    """[{code, name}] from the rättspraxis API's court list, sorted by code."""
    courts = json.loads(raw)
    return sorted(({"code": c["domstolKod"], "name": c["domstolNamn"]} for c in courts), key=lambda c: c["code"])


def _fetch(client, host, url):
    robots = _Robots(client, host)
    if not robots.allows(url):
        raise Blocked(f"robots.txt disallows {url}")
    return client.get(url)


def fetch_index(client, now):
    """Fetch the rättskällor index politely; raise Blocked if robots.txt disallows it."""
    return {"source": INDEX_URL, "fetched_at": now, "pages": parse_index(_fetch(client, INDEX_HOST, INDEX_URL))}


def fetch_courts(client, now):
    """Fetch the court list of the rättspraxis API politely."""
    return {"source": COURTS_URL, "fetched_at": now, "courts": parse_courts(_fetch(client, COURTS_HOST, COURTS_URL))}


def court_url(code):
    """The rättspraxis search for one court's guiding decisions, as lagrummet.se links it."""
    query = f'domstolskodLista=["{code}"]&arVagledande=true&sortering="desc"'
    return COURT_SEARCH + urllib.parse.quote(urllib.parse.quote(query, safe="=&"), safe="")


def tally_corpus(corpus):
    """Counts the report needs, from documents that pass schema validation."""
    counts = {"series": {}, "years": {}, "kommun": {}, "court": {}, "court_name": {}, "type": {}}
    for meta in progress._valid_metas(corpus):
        layer, number = meta["layer"], str(meta.get("number") or "")
        counts["type"][meta["type"]] = counts["type"].get(meta["type"], 0) + 1
        key = progress._series_key(meta)
        if key:
            counts["series"][key] = counts["series"].get(key, 0) + 1
            year = _YEAR.search(number)
            if year:
                counts["years"].setdefault(key, set()).add(int(year.group(1)))
        if layer == "municipality":
            code = meta["id"][:4]
            counts["kommun"][code] = counts["kommun"].get(code, 0) + 1
        if layer == "case_law" and meta.get("court"):
            court = meta["court"]
            counts["court"][court] = counts["court"].get(court, 0) + 1
            counts["court_name"].setdefault(court, meta.get("issuer") or court)
    return counts


def _years(counts, key):
    years = counts["years"].get(key)
    if not years:
        return None
    return str(min(years)) if min(years) == max(years) else f"{min(years)}–{max(years)}"


def _issue(curated, key):
    number = curated.get("issues", {}).get(key)
    return ISSUES_URL + str(number) if number else None


def build_report(index, curated, counts, targets, counties, municipalities, municipal_manifest, geo,
                 courts=None, kommuner=None):
    series_status = {}
    agencies, shared, sources, unclassified, county_pages = [], [], [], [], {}
    target_by_series = {t["series"]: t["target"] for t in targets if t.get("series")}
    for page in index["pages"]:
        slug = page["slug"]
        link = {"url": page["url"], "description": page.get("description")}
        if slug in curated["series"]:
            entry = curated["series"][slug]
            documents = counts["series"].get(("agency", entry["series"]), 0)
            status = entry.get("status") or ("collected" if documents else "no_adapter")
            agencies.append({"series": entry["series"], "agency": entry["agency"], "status": status,
                             "documents": documents, "target": target_by_series.get(entry["series"]),
                             "note": entry.get("note"), **link,
                             "issue": _issue(curated, "series:" + entry["series"])})
            series_status.setdefault(entry["series"], status)
        elif slug in curated["shared"]:
            shared.append({**curated["shared"][slug], **link})
        elif slug in curated["sources"]:
            sources.append({**curated["sources"][slug], "slug": slug, **link, "issue": _issue(curated, "source:" + slug)})
        elif _COUNTY_SLUG.match(slug):
            county_pages[_COUNTY_SLUG.match(slug).group(1)] = link
        else:
            unclassified.append({"slug": slug, "title": page["title"], "status": "unclassified", **link})
    agencies.sort(key=lambda a: (_ORDER.index(a["status"]), a["series"], a["agency"]))
    seen, unique_shared = set(), []
    for entry in sorted(shared, key=lambda s: (s["agency"], s["published_in"])):
        if (entry["agency"], entry["published_in"]) not in seen:
            seen.add((entry["agency"], entry["published_in"]))
            unique_shared.append({**entry, "status": series_status.get(entry["published_in"], "no_adapter"),
                                  "issue": _issue(curated, "series:" + entry["published_in"])})
    sources.sort(key=lambda s: (_ORDER.index(s["status"]), s["layer"], s["name"]))

    county_rows = []
    for region in geo["regions"]:
        code = region["code"]
        config = counties["counties"].get(code)
        key = ("region", f"{code}FS")
        documents = counts["series"].get(key, 0)
        if config is None:
            status, text = "no_adapter", None
        else:
            status = "partial" if documents else "no_adapter"
            text = "HTML text" if config["layout"] == "pages" else "PDF links only"
        page = county_pages.get(code, {})
        county_rows.append({"code": code, "county": region["name"], "series": f"{code}FS", "status": status,
                            "documents": documents, "years": _years(counts, key), "text": text,
                            "url": config["landing"] if config else page.get("url"),
                            "description": page.get("description"), "issue": _issue(curated, "county:" + code)})

    gaps = {}
    for gap in municipal_manifest.get("gaps", []):
        gaps.setdefault(gap["municipality_code"], {}).setdefault(gap["reason"], 0)
        gaps[gap["municipality_code"]][gap["reason"]] += 1
    regions = {r["code"]: r["name"] for r in geo["regions"]}
    websites = (kommuner or {}).get("websites", {})
    # Curated per-kommun status and note: why a kommun is not (fully) collected.
    kommun_notes = curated.get("kommuner", {})
    configured, missing = [], {}
    for kommun in sorted(geo["kommuner"], key=lambda k: k["code"]):
        code = kommun["code"]
        config = municipalities["kommuner"].get(code)
        row = {"code": code, "kommun": kommun["name"], "url": websites.get(code), "issue": _issue(curated, "kommun:" + code)}
        known = kommun_notes.get(code, {})
        if config is None and known:
            configured.append({**row, "collection": None, "status": known.get("status", "no_adapter"),
                               "documents": 0, "note": known.get("note")})
            continue
        if config is None:
            missing.setdefault(kommun["regionCode"], []).append(row)
            continue
        documents = counts["kommun"].get(code, 0)
        notes = [f"{n} documents not fetched: {reason}" for reason, n in sorted(gaps.get(code, {}).items())]
        if known.get("note"):
            notes.append(known["note"])
        configured.append({**row, "collection": config["collection"],
                           "status": "partial" if documents else "no_adapter", "documents": documents,
                           "note": "; ".join(notes) or None})
    missing_rows = [{"region_code": code, "county": regions[code], "kommuner": rows}
                    for code, rows in sorted(missing.items())]

    court_notes = curated.get("courts", {})
    court_names = {c["code"]: c["name"] for c in (courts or {}).get("courts", [])}
    court_names.update({code: name for code, name in counts["court_name"].items() if code not in court_names})
    court_rows = []
    for code, name in court_names.items():
        documents = counts["court"].get(code, 0)
        note = court_notes.get(code, {})
        status = note.get("status") or ("collected" if documents else "no_adapter")
        court_rows.append({"code": code, "court": name, "status": status, "documents": documents,
                           "note": note.get("note"), "url": court_url(code), "issue": _issue(curated, "court:" + code)})
    court_rows.sort(key=lambda c: (_ORDER.index(c["status"]), -c["documents"], c["code"]))
    layers = {
        "sfs": sum(counts["type"].get(t, 0) for t in progress.SFS_TYPES),
        "fundamental": counts["type"].get("fundamental_law", 0),
        "eu": sum(n for t, n in counts["type"].items() if t.startswith("eu_")),
        "case_law": sum(counts["court"].values()),
    }
    summary = {}
    for entry in agencies:
        summary[entry["status"]] = summary.get(entry["status"], 0) + 1
    return {
        "index": {"source": index["source"], "fetched_at": index["fetched_at"], "pages": len(index["pages"])},
        "summary": {"series": len(agencies), "by_status": summary,
                    "shared": len(unique_shared), "kommuner": len(geo["kommuner"]),
                    "kommuner_configured": sum(1 for k in configured if k["collection"]),
                    "courts": len(court_rows), "courts_collected": sum(1 for c in court_rows if c["documents"])},
        "agency_series": agencies,
        "shared_series": unique_shared,
        "counties": county_rows,
        "municipalities": {"configured": configured, "not_configured": missing_rows},
        "courts": court_rows,
        "layers": layers,
        "other_sources": sources,
        "unclassified": unclassified,
    }


def _cell(value):
    return "-" if value is None else str(value).replace("|", "\\|")


def _link(text, url):
    return f"[{_cell(text)}]({url})" if url else _cell(text)


def _issue_cell(url):
    return f"[#{url.rsplit('/', 1)[1]}]({url})" if url else "-"


def render_markdown(report):
    idx, summary = report["index"], report["summary"]
    out = [
        "# Agencies and sources",
        "",
        "Which Swedish legal sources the corpus processes and which it does not, with the reason for each "
        "gap and the issue that tracks it. Generated by `collector/agencies.py` from lagrummet.se's "
        f"[rättskällor index]({idx['source']}) (fetched {idx['fetched_at'][:10]}, {idx['pages']} entries), "
        "the rättspraxis court list, the corpus and the collector configuration; do not edit by hand. Each "
        "name links to the official page of the source. Per-series counts are in "
        "[PROGRESS.md](PROGRESS.md) and the details of each gap in [COVERAGE.md](COVERAGE.md). "
        "The same data is browsable on the [landing page](https://grundlagar.vercel.app/#catalog).",
        "",
        "## Summary",
        "",
        f"{summary['series']} agency regulation series, {summary['shared']} agencies that publish in another "
        f"agency's series, {summary['kommuner_configured']} of {summary['kommuner']} kommuner configured, "
        f"{summary['courts_collected']} of {summary['courts']} courts with collected case law.",
        "",
        "| agency series | count |",
        "| --- | ---: |",
    ]
    out += [f"| {STATUSES[s]} | {summary['by_status'][s]} |" for s in _ORDER if s in summary["by_status"]]
    layers = report["layers"]
    out += [
        "",
        f"Other layers in the corpus: {layers['fundamental']} fundamental laws, {layers['sfs']} SFS statutes, "
        f"{layers['case_law']} case-law documents, {layers['eu']} EU documents "
        "(a curated list, from the Publications Office Cellar).",
        "",
        "## Agency regulation series",
        "",
        "| series | agency | status | documents | target | issue | note |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for a in report["agency_series"]:
        out.append(f"| {_link(a['series'], a['url'])} | {_cell(a['agency'])} | {STATUSES[a['status']]} | "
                   f"{a['documents']} | {_cell(a['target'])} | {_issue_cell(a['issue'])} | {_cell(a['note'])} |")
    out += [
        "",
        "## Agencies publishing in another series",
        "",
        "Their regulations are collected when the series they publish in is; the issue is that series' issue.",
        "",
        "| agency | published in | status of that series | issue |",
        "| --- | --- | --- | --- |",
    ]
    out += [f"| {_link(s['agency'], s['url'])} | {s['published_in']} | {STATUSES[s['status']]} | "
            f"{_issue_cell(s['issue'])} |" for s in report["shared_series"]]
    out += [
        "",
        "## County regulations (Länsstyrelserna)",
        "",
        "| code | county | series | status | documents | years | text | issue |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for c in report["counties"]:
        out.append(f"| {c['code']} | {_link(c['county'], c['url'])} | {c['series']} | {STATUSES[c['status']]} | "
                   f"{c['documents']} | {_cell(c['years'])} | {_cell(c['text'])} | {_issue_cell(c['issue'])} |")
    m = report["municipalities"]
    out += [
        "",
        "## Municipal regulations (kommuner)",
        "",
        f"{summary['kommuner_configured']} of {summary['kommuner']} kommuner have a collector configuration "
        "(`collector/data/municipalities.json`); the table also lists kommuner checked and not collected, "
        "with the reason. The others are not collected: no configuration yet. "
        "Each name links to the kommun's official website.",
        "",
        "| code | kommun | collection | status | documents | issue | note |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    out += [f"| {k['code']} | {_link(k['kommun'], k['url'])} | {_cell(k['collection'])} | {STATUSES[k['status']]} | "
            f"{k['documents']} | {_issue_cell(k['issue'])} | {_cell(k['note'])} |" for k in m["configured"]]
    out += ["", "Not configured yet, per county:", ""]
    for row in m["not_configured"]:
        names = ", ".join(_link(k["kommun"], k["url"]) + (f" ({_issue_cell(k['issue'])})" if k["issue"] else "")
                          for k in row["kommuner"])
        out.append(f"- {row['county']} ({len(row['kommuner'])}): {names}")
    out += [
        "",
        "## Courts (case law)",
        "",
        "Every court in Sveriges Domstolar's rättspraxis API. Referat and notiser are collected; rulings "
        "published in full, attachments and non-guiding decisions are left out by design. Each name links "
        "to the court's guiding decisions on rättspraxis.",
        "",
        "| code | court | status | documents | issue | note |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    out += [f"| {c['code']} | {_link(c['court'], c['url'])} | {STATUSES[c['status']]} | {c['documents']} | "
            f"{_issue_cell(c['issue'])} | {_cell(c['note'])} |" for c in report["courts"]]
    out += [
        "",
        "## SFS, EU and other sources",
        "",
        "| source | layer | status | issue | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    out += [f"| {_link(s['name'], s['url'])} | {s['layer']} | {STATUSES[s['status']]} | {_issue_cell(s['issue'])} | "
            f"{_cell(s.get('note'))} |" for s in report["other_sources"]]
    if report["unclassified"]:
        out += ["", "## Unclassified lagrummet.se entries", "",
                "Entries the curated list in `collector/data/agencies.json` does not know yet:", ""]
        out += [f"- {_link(u['title'], u['url'])}" for u in report["unclassified"]]
    return "\n".join(out) + "\n"


def landing_catalog(report):
    """The report reshaped for the landing page catalog: one flat list per section, same row keys."""
    def row(name, entry, **extra):
        return {"name": name, "status": entry["status"], "documents": entry.get("documents"),
                "url": entry.get("url"), "issue": entry.get("issue"), "description": entry.get("description"),
                "note": entry.get("note"), **extra}

    counties = {c["code"]: c["county"] for c in report["counties"]}
    m = report["municipalities"]
    kommuner = [row(k["kommun"], k, code=k["code"], county=counties.get(k["code"][:2])) for k in m["configured"]]
    kommuner += [row(k["kommun"], {**k, "status": "no_adapter", "documents": 0}, code=k["code"], county=r["county"])
                 for r in m["not_configured"] for k in r["kommuner"]]
    return {
        "generated": report["index"]["fetched_at"][:10],
        "statuses": _ORDER,
        "sections": {
            "series": [row(a["series"], a, agency=a["agency"]) for a in report["agency_series"]],
            "shared": [row(s["agency"], s, published_in=s["published_in"]) for s in report["shared_series"]],
            "counties": [row(c["county"], c, code=c["code"], series=c["series"], years=c["years"])
                         for c in report["counties"]],
            "kommuner": sorted(kommuner, key=lambda k: k["code"]),
            "courts": [row(c["court"], c, code=c["code"]) for c in report["courts"]],
            "sources": [row(s["name"], s, layer=s["layer"]) for s in report["other_sources"]],
        },
    }


def _read_json(path, default=None):
    path = Path(path)
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv, client=None):
    parser = argparse.ArgumentParser(prog="agencies.py", description="Write AGENCIES.md and its JSON report.")
    parser.add_argument("--refresh", action="store_true",
                        help="fetch the lagrummet.se index and the rättspraxis court list again")
    parser.add_argument("--rate", type=float, default=2.0, help=f"seconds between requests (at least {MIN_RATE})")
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--courts", default=DEFAULT_COURTS)
    parser.add_argument("--kommuner", default=DEFAULT_KOMMUNER)
    parser.add_argument("--curated", default=DEFAULT_CURATED)
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--targets", default=progress.DEFAULT_TARGETS)
    parser.add_argument("--counties", default=DEFAULT_COUNTIES)
    parser.add_argument("--municipalities", default=DEFAULT_MUNICIPALITIES)
    parser.add_argument("--municipal-manifest", default=DEFAULT_MUNICIPAL_MANIFEST)
    parser.add_argument("--geo", default=DEFAULT_GEO)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--out", default="AGENCIES.md")
    parser.add_argument("--landing", default=DEFAULT_LANDING, help="catalog JSON for the landing page")
    args = parser.parse_args(argv)
    if args.rate < MIN_RATE:
        parser.error(f"--rate must be at least {MIN_RATE}")
    if args.refresh:
        client = client or PoliteClient(USER_AGENT, min_interval=args.rate)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            index = fetch_index(client, now)
            courts = fetch_courts(client, now)
        except (Blocked, ListingError, ValueError, *NETWORK_ERRORS) as error:
            print(f"sources not fetched: {error}", file=sys.stderr)
            return 1
        _write_json(args.cache, index)
        _write_json(args.courts, courts)
    report = build_report(
        _read_json(args.cache), _read_json(args.curated), tally_corpus(args.corpus), _read_json(args.targets),
        _read_json(args.counties), _read_json(args.municipalities),
        _read_json(args.municipal_manifest, {}), _read_json(args.geo),
        _read_json(args.courts, {}), _read_json(args.kommuner, {}),
    )
    _write_json(args.report, report)
    Path(args.out).write_text(render_markdown(report), encoding="utf-8")
    if args.landing:
        Path(args.landing).parent.mkdir(parents=True, exist_ok=True)
        _write_json(args.landing, landing_catalog(report))
    for status in _ORDER:
        if status in report["summary"]["by_status"]:
            print(f"{STATUSES[status]}: {report['summary']['by_status'][status]}")
    return 0
