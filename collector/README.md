# lagar collector

Collects Swedish statutes (SFS) from Riksdagen open data into `corpus/` Markdown files,
records a SHA-256 manifest of the authoritative SFS PDFs, adds each statute's amendment
register from SFSR, writes a metadata-only amendment history for git, collects the published case
law of the Swedish courts, collects EU acts in Swedish from the Publications Office Cellar and
collects municipal regulations from the kommuner's own författningssamlingar.
Python standard library only.

## Usage

Run from the repository root (`-I` ignores `PYTHONPATH`, so use the entry script):

```
python3 -I collector/collect.py sfs --fundamental
python3 -I collector/collect.py sfs [--from YYYY-MM-DD --to YYYY-MM-DD] [--limit N] \
    [--since YYYY-MM-DD] [--rate SECONDS] [--state collector/data/sfs-state.json] \
    [--corpus corpus] [--report FILE]
python3 -I collector/collect.py sfs --changed-since "YYYY-MM-DD[ HH:MM:SS]" [--report FILE]
```

- `--fundamental` fetches only the four fundamental laws (always refetched).
- `--since` keeps listing items whose `systemdatum` is on or after the date.
- `--changed-since` pages the listing newest-first by `systemdatum` and stops at the first
  document older than the bound, so an incremental sync reads only the pages it needs. It
  cannot be combined with `--fundamental` or `--since`.
- `--report` writes a JSON summary: written SFS numbers, unchanged/skipped counts, failed ids,
  `blocked` and the newest `systemdatum` seen (`latest_systemdatum`).
- `--limit` stops after N written documents.
- `--rate` is the minimum interval between requests (default 1.0 s).

A refetched document whose source SHA-256 matches the stored file is left untouched (counted as
unchanged), so reruns never churn `fetched_at`.

## Scheduled sync

`.github/workflows/sync-sfs.yml` runs daily, and on manual dispatch with an optional earlier
`since`. It starts from `main`, or from the `data/sfs-sync` branch while a sync pull request is
open, and collects with `--changed-since` from the marker in `collector/data/sfs-sync.json`.

When the corpus changed, the workflow:
- refreshes the audit and progress reports;
- moves the marker to the newest `systemdatum` seen, or to `retry_from` when a document failed
  with a network error;
- adds one `data(sfs):` commit to `data/sfs-sync`, opening a pull request if none is open.

The marker only moves inside that commit, so a failed run, a rejected push or an abandoned pull
request never skips documents: the next run collects them again. A run that finds nothing new
commits nothing. Failures are listed in the run summary and in the commit body.

Two GitHub constraints apply. The workflow needs "Allow GitHub Actions to create and approve pull
requests" enabled in the repository settings. Pull requests opened with the default token do not
trigger other workflows.

## Listing cap

Riksdagen serves at most 10,000 listing results (50 pages of 200); page 51 answers HTTP 400.
A full run therefore needs date windows, e.g. `--to 2016-12-31` and then `--from 2016-12-22`
(overlap is harmless: finished documents are skipped).

## Resume

State is kept in `collector/data/sfs-state.json` (git-ignored) and rewritten atomically
after every document: `{"done": {id: systemdatum}, "failed": {id: error}, "blocked": null|msg}`.
A document is skipped when its `systemdatum` matches the state and its corpus file exists.
Per-document errors are recorded under `failed` and the run continues; rerun to retry them.
Digitised OCR prints that have no plain-text version are recorded there too, as a coverage gap.

Items sharing a date may shift between listing pages during a long run; a rerun picks up any miss.

## Authoritative PDFs

The SFS published on <https://svenskforfattningssamling.se> is the authoritative version. The
`sfspdf` command records a SHA-256 manifest of its PDFs; it never changes `corpus/`.

```
python3 -I collector/collect.py sfspdf --year YYYY [--year YYYY ...] [--limit N] [--cache DIR] \
    [--manifest sources/sfs-pdf-manifest.json] [--state collector/data/sfspdf-state.json] \
    [--rate SECONDS] [--report FILE]
python3 -I collector/collect.py sfspdf --rss [--report FILE]
```

- `--year` walks the year index (`regulations/<year>/index.html`, 15 acts per page, newest
  first) through its "next" links; `--rss` reads only the RSS feed of recent acts, for an
  incremental run.
- Each act's detail page (`doc/<year><number>.html`) is read for its PDF links. An act can have
  several files, for example a correction sheet (rättelseblad). Every PDF is downloaded once and
  hashed; a response that does not start with `%PDF-`, a detail page showing another number and a
  link off the site are recorded as failures.
- The manifest `sources/sfs-pdf-manifest.json` is committed. Entries are sorted by year and
  number; each has `number`, `detail_url`, `published` and `files` (`url`, `bytes`, `sha256`,
  `content_type`, `retrieved_at`). Numbers already in the manifest are skipped, so reruns
  fetch only new acts.
- PDF bytes are never committed. `--cache DIR` keeps them as `DIR/<year>/<file>.pdf`; use the
  git-ignored `sources/cache/`.
- `--limit` stops after N new entries. The manifest is saved every 25 entries and when the run
  ends, including on an error or interrupt.
- `--report` writes `{"recorded": [...], "skipped": n, "failed": [...], "blocked": bool}`.
- The state file (git-ignored) keeps `failed` (number to error) and `blocked`.

The site has no robots.txt (HTTP 404); one is honoured if it appears. The PDFs are signed by
the publisher, but the signature is not verified or recorded. `Last-Modified` and `ETag` change
nightly, so they are not used. A full crawl of 2018 to today is about 30,000 requests.

## Amendment register (SFSR)

Riksdagen texts carry no entry-into-force date and only mention amending acts inline. The SFS
register (SFSR) of Regeringskansliets rättsdatabaser lists every amending act of a statute. The
`sfsr` command reads it for statutes already in the corpus:

```
python3 -I collector/collect.py sfsr --pilot | --number YYYY:N [--number ...] | --all \
    [--refresh] [--limit N] [--corpus corpus] [--manifest sources/sfsr-manifest.json] \
    [--state collector/data/sfsr-state.json] [--rate SECONDS] [--report FILE]
```

- The source is `https://rkrattsbaser.gov.se/sfsr?bet=<number>`, one server-rendered HTML page
  per statute, read with `html.parser`. The site has no robots.txt (one is honoured if it
  appears); `--rate` defaults to, and may not go below, 2 s between requests.
- `--pilot` reads Regeringsformen (1974:152), Brottsbalken (1962:700) and Miljöbalken
  (1998:808); `--all` reads every statute in the corpus in number order. A statute that is not
  in the corpus is recorded as failed without a request.
- Only the frontmatter changes; the body is kept byte for byte. `in_force` gets the statute's
  own `Ikraft` (left as it is when the register has none) and `amendments` gets one entry per
  "Ändring, SFS ..." box, in register order: `number`, `title` (Rubrik), `scope`
  (Omfattning), `preparatory_works` (Förarbeten), `celex` (CELEX-nr), `in_force` and
  `in_force_raw`. Whitespace is collapsed; missing fields are `null`.
- `Ikraft` values: `in_force` is the date the value starts with, `in_force_raw` the value as
  written. `1983-07-01 överg.best.` (transitional provisions apply) gives `1983-07-01`; a value
  that does not start with a date, such as an entry into force set by a later government
  decision, gives `in_force: null` and keeps the text. Missing values (most entries before
  about 1982) give `null` for both.
- Register entries with another header than "Ändring" are not stored; they are listed in the
  manifest entry's `other_entries`. A page that shows another statute, or is not a single
  register entry (for example a search result), is recorded as failed.
- The committed manifest `sources/sfsr-manifest.json` keeps, per statute, `number`, `url`,
  `bytes`, `sha256` and `retrieved_at` of the fetched page, the number of amendments and
  `other_entries`. Statutes already in it are skipped unless `--refresh` is given, so a bulk
  run can be resumed. The HTML is not stored.
- `--report` writes `{"written": [...], "unchanged": [...], "skipped": n, "failed": [...],
  "blocked": bool}`. The state file (git-ignored) keeps `failed` (number to error) and
  `blocked`; an HTTP 403 or a robots.txt disallow stops the run (exit code 2).

The `sfs` collector never erases this data: when it rewrites a statute from Riksdagen it keeps
the stored `in_force` and `amendments`. A new successor site (`beta.rkrattsbaser.gov.se`) is
being built, so the page layout may change.

## Amendment history

`collector/history.py` turns the register into history: one commit for each statute and one
per amendment, dated at entry into force, as a `git fast-import` stream. The files on the
history branch hold frontmatter only (identity, `in_force`, `amended_through` and the
amendments applied so far). Historical text is not reconstructed: no open source has it.

```
python3 -I collector/history.py --pilot --dry-run          # list the commits
python3 -I collector/history.py --pilot --out build/history.fi
git fast-import --quiet < build/history.fi                 # creates history/pilot
```

- Commit dates: the amendment's entry into force; else its publication date in
  `sources/sfs-pdf-manifest.json` (acts from 2018 on); else 1 January of its SFS year. The
  statute's own commit uses its `in_force`, else `issued`. Each commit body names the date and
  its source.
- An amendment dated before its statute's own commit moves to that date. Dates before 1970
  are stored as 1970-01-01 (git cannot record earlier dates); the body keeps the real date.
  Amendments that enter into force in the future get future commit dates.
- Commits from several statutes are merged into one branch in date order. The stream starts
  with `reset`, so it always builds the branch from scratch; to rebuild an existing branch
  run `git fast-import --force`. `--branch` and `--author` change the defaults
  (`history/pilot`, `lagar history <history@lagar.invalid>`).
- Statutes without `amendments` in the corpus are refused: run `collect.py sfsr` first.

The branch is not pushed by any workflow.

## EU law (Cellar)

The `eu` command collects EU regulations, directives and decisions in their Swedish language
version from the Cellar, the Publications Office repository behind EUR-Lex:

```
python3 -I collector/collect.py eu --list collector/data/eu-acts.json [--consolidated] \
    [--refresh] [--limit N] [--cache sources/cache/eu] [--corpus corpus] \
    [--manifest sources/eu-manifest.json] [--state collector/data/eu-state.json] \
    [--rate SECONDS] [--report FILE]
python3 -I collector/collect.py eu --celex 32016R0679[,32022L2555 ...] [options]
```

- Metadata: one SPARQL query per act to `https://publications.europa.eu/webapi/rdf/sparql`
  (date of document, entry into force, end of validity, ELI, adopting institutions, Swedish
  title and manifestation types, amending acts and consolidated versions).
- Text: `https://publications.europa.eu/resource/celex/<CELEX>` with `Accept-Language: swe`
  and `Accept: application/xhtml+xml` (or `text/html` for older acts that only have the old
  EUR-Lex HTML) answers 303 with the Swedish manifestation. It is converted to Markdown with
  `html.parser`: divisions (KAPITEL, AVDELNING, AVSNITT, BILAGA) as `##`, articles as `###`,
  article and chapter titles in bold, point labels kept with their text, other table rows on
  one line with cells separated by ` | `. The OJ page header and the `►M1 … ◄` / `▼B`
  markers of consolidated texts are dropped.
- **eur-lex.europa.eu is never contacted.** Its front end answers automated clients with a
  WAF challenge. Every request, and every redirect, must stay on `publications.europa.eu` or
  `op.europa.eu` (where its robots.txt lives); redirects are followed over https only.
- Acts without a Swedish expression, or with Swedish only as PDF or print (REACH, for
  example), are recorded as gaps in the state file and in the manifest's `gaps`; nothing is
  translated. `--consolidated` also collects each act's latest consolidated version that
  applies today (CELEX `0…-YYYYMMDD`) and removes older consolidated versions of that act.
- Frontmatter: `id` `eu-<celex lowercased>`, `number` in the Swedish citation form taken from
  the Swedish title when it agrees with the CELEX number (else rebuilt from it: `(EU) 2016/679`,
  `(EG) nr 1907/2006`, `95/46/EG`), `celex`, `issued` (date of document; for a consolidated
  version, the base act's), `in_force` (earliest entry into force), `repealed` (end of
  validity unless open-ended), `amended_by` (CELEX numbers of amending acts), `eli`, `issuer`
  (adopting institutions in Swedish), `source` (the manifestation URL), `source_sha256`.
  `authoritative` is true for the Official Journal text, false for consolidated versions.
- The committed manifest `sources/eu-manifest.json` lists, per act, `celex`, `id`, `url`,
  `content_type`, `bytes`, `sha256` and `retrieved_at` (kept while the bytes are unchanged),
  plus the gaps. `--cache DIR` keeps the bytes as `DIR/<CELEX>.<format>` (use the git-ignored
  `sources/cache/`).
- Resume: the state file (git-ignored) keeps `done` (CELEX to SHA-256), `failed`, `gaps` and
  `blocked`. Collected acts are skipped unless `--refresh`; a refresh rewrites a document only
  when its frontmatter (apart from `fetched_at`) or its converted text changed.
- `--rate` defaults to, and may not go below, 1 s. An HTTP 403, a long `Retry-After` or a
  robots.txt disallow stops the run (exit code 2).
- `--report` writes `{"written": [...], "unchanged": [...], "skipped": n, "gaps": [...],
  "failed": [...], "blocked": bool}`.

The curated list `collector/data/eu-acts.json` holds the acts the app highlights (data
protection, digital, consumer, labour, environment, private international law). A wider
in-force sweep is not implemented yet. Reuse is free with acknowledgement of the source
(Commission Decision 2011/833/EU).

## Case law

The `case-law` command (alias `caselaw`) collects the anonymised summaries that the courts
publish as guiding case law, from the open API of Sveriges Domstolar (dataset "Rättspraxis från
Sveriges Domstolar", CC0):

```
python3 -I collector/collect.py case-law [--court CODE ...] [--from YYYY-MM-DD] [--to YYYY-MM-DD] \
    [--since YYYY-MM-DD] [--limit N] [--page-size N] [--rate SECONDS] \
    [--state collector/data/case-law-state.json] [--corpus corpus] [--report FILE]
```

- Source: `GET https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar?publiceringsformer=referat,notis`
  (OpenAPI spec at `/openapi/puh-openapi.yaml`), paged with `page` (from 0) and `pagesize`
  (default 20), newest decision first. Each listing entry is the whole publication, so the listing
  is the only endpoint requested.
- Only referat (`case_report`, `corpus/case-law/reports/`) and notiser (`case_notice`,
  `corpus/case-law/notices/`) are stored. Rulings published in full (`DOM_ELLER_BESLUT`), leave to
  appeal (`PROVNINGSTILLSTAND`), preliminary rulings (`FORHANDSAVGORANDE`) and non-guiding decisions
  (`EJ_VAGLEDANDE`) are skipped and counted as `excluded`. Attachments (`/api/v1/bilagor/...`) are
  never requested; tests assert that every request goes to the listing.
- The texts are the courts' anonymised publications. As a safeguard, a publication whose text
  contains a personal identity number (valid date and check digit) is recorded as failed and not
  written.
- `--court` takes the codes of `GET /api/v1/domstolar` (`HDO` Högsta domstolen, `HFD` Högsta
  förvaltningsdomstolen, `ADO`, `MIOD`, ...); repeat it for several courts. `--from`/`--to` bound
  the decision date (`avgorandedatum`); the run stops at the first decision older than `--from`.
  `--since` (alias `--changed-since`) asks the API for publications published on or after the day
  (`publicerad_fran_och_med`), for an incremental sync.
- Mapping: `number` is the report reference, the ordinal form (`NJA 2026:38`) when the API gives
  one, else the first reference (`HFD 2026 ref. 43`, `HFD 2026 not. 24`, `NJA 2019 s. 2`); `id` is
  its slug (`nja-2026-38`, `hfd-2026-ref-43`, `ra-2010-ref-5`). `title` is the summary
  (`sammanfattning`, the report's headline), `issued` the decision date, `court` the court code,
  `issuer` the court name, `ecli` the ECLI when it has the standard form. `source` is
  `/api/v1/publiceringar/{id}` and `source_sha256` hashes the publication as the API serialises it
  (sorted keys, compact UTF-8 JSON), which is byte for byte the response of that URL.
- Body: a facts block (court, decision date, case numbers, all references, name, ECLI), then
  sections for Lagrum (with SFS numbers), Nyckelord, Rättsområden, Förarbeten, Litteratur,
  Hänvisningar and Europarättsliga avgöranden when present, then the text (`innehall`, HTML
  converted to Markdown, headings moved down two levels) under `## Referat` or `## Notis`.
- A publication without a reference in the schema's form (`[A-ZÅÄÖ]{2,5} YYYY:N` or
  `YYYY s./ref./not./nr/N N`), or with a reference already stored from another publication, is
  recorded as failed.
- State (git-ignored) is `{"done": {publication id: publiceringstid}, "failed": {id: error},
  "blocked": null|msg}`; a publication is skipped when its `publiceringstid` matches and its file
  exists. A document whose frontmatter (apart from `fetched_at`) and body are unchanged is left
  untouched. After a mapping change, delete the state file and rerun to rewrite affected files.
- `--limit` stops after N written documents (unchanged ones do not count). `--report` writes
  `{"written": [...], "unchanged": n, "skipped": n, "excluded": n, "failed": [...], "blocked": bool,
  "latest_published": "..."}`.
- The site has no robots.txt (HTTP 404); one is honoured if it appears. An HTTP 403 stops the run
  (exit code 2). Entries may shift between pages while the courts publish; a rerun picks up any miss.

## Municipal regulations (kommunala författningssamlingar)

Each kommun publishes its own författningssamling on its own website; there is no national
dataset. `municipal` reads the kommuner listed in `collector/data/municipalities.json`.

```
python3 -I collector/collect.py municipal --kommun 0180 [--kommun 1480 ...] [--limit N] \
    [--refresh] [--report FILE] [--rate SECONDS] [--config collector/data/municipalities.json] \
    [--state collector/data/municipal-state.json] [--manifest sources/municipal-manifest.json]
python3 -I collector/collect.py municipal --all [--limit N]
```

- Scope: only rules that bind residents (lokala ordningsföreskrifter, föreskrifter om avfall,
  renhållning and naturreservat, hamnordningar, taxor and avgifter). Internal governance documents
  (reglementen, arbetsordningar, instruktioner, bolagsordningar, ägardirektiv, delegationsordningar,
  stadgar) are left out through each kommun's `sections` or `kinds`.
- Pilot: Stockholm (0180), Göteborg (1480) and Malmö (1280).
- robots.txt is read once per host before any other request, with RFC 9309 wildcards (`*`, `$`)
  and longest-match precedence (the standard library parser ignores wildcards). A disallowed
  listing stops that kommun; a disallowed document is not fetched and is recorded as a gap.
  Requests go only to the hosts configured for the kommun, redirects included.
- PDF text is never extracted. A fetched PDF goes into the manifest with its SHA-256 and becomes
  `source`/`source_sha256`. When robots.txt disallows the PDF, `source` is the listing page (or the
  Domino detail page) and `source_sha256` hashes that page; the body says the document was not
  fetched.
- Mapping: `id` is `<kommun code>-<slug of number>`, for example `0180-kfs-2026-12`; `number` is the
  local number as printed (`KFS 2026:12`), the Domino serial number (`N010G00545`) or, when the
  site prints no number (Malmö), the Sitevision id of the file (`18.630778b81a03e20b4c51db6`).
  `issuer` is the kommun, `municipality_code` its SCB code and `region_code` its county.
  `issued` and `in_force` stay `null`: the listings do not give them reliably.
- Body: kommun, collection and number (plus version, adopting body and the handbook's
  "Gällande från" date for Domino), a link to the listing or detail page, the kommun's own note
  (Domino `BodyField`, converted with `htmlmd`) and links to the PDFs.
- Some servers answer with brotli even when only gzip is accepted. Brotli streams made of
  uncompressed meta-blocks (start.stockholm's robots.txt) are decoded; a compressed one is
  retried twice and then counted as a failure.
- State (git-ignored) is `{"done": {id: source sha256}, "failed": {id or url: error},
  "gaps": {id: reason}, "blocked": {code: reason}}`. A document is skipped when it is done and its
  file exists, unless `--refresh`; a refreshed document whose frontmatter (apart from `fetched_at`)
  and body are unchanged is left untouched.
- `--limit` stops after N written documents per kommun. `--report` writes `{"written": [...],
  "unchanged": [...], "skipped": n, "gaps": [...], "failed": [...], "blocked": {code: reason}}`.
- An HTTP 403, an unreadable robots.txt or listing, or a redirect off the configured hosts blocks
  that kommun (exit code 2); the other kommuner still run.

### Adding a kommun

Add an entry under `kommuner`, keyed by the four-digit SCB code:

```json
"0180": {
  "name": "Stockholm",
  "issuer": "Stockholms stad",
  "region_code": "01",
  "collection": "Stockholms stads kommunala författningssamling (KFS)",
  "strategy": "html_index",
  "hosts": ["start.stockholm"],
  "listings": ["https://start.stockholm/.../kommunal-forfattningssamling/"],
  "section_level": 2,
  "sections": ["Reglerande styrdokument"],
  "link_pattern": "^https://start\\.stockholm/globalassets/.*\\.pdf$",
  "number": [{"from": "text", "pattern": "KFS\\s*(\\d{4}):(\\d+)", "format": "KFS {0}:{1}"}],
  "title_strip": ["\\s*\\(?pdf\\)?\\s*$", ",?\\s*KFS\\s*\\d{4}:\\d+\\s*$"]
}
```

1. Check the site's robots.txt and terms first. If the site forbids automation or answers with a
   captcha or block, do not add it: record it as a gap in `COVERAGE.md`.
2. Pick a strategy:
   - `html_index`: a page that links straight to the documents. A link is kept when the latest
     heading at or above `section_level` (h1 to h`N`) is one of `sections` (empty keeps all) and
     the absolute URL matches `link_pattern`. `number` is a list of rules tried in order, each
     reading the link text (`"from": "text"`) or the URL (`"from": "href"`); with `format` the
     regex groups fill it, without it the first group (or the whole match) is the number.
     `title_strip` regexes are removed from the link text to get the title.
   - `domino_view`: an IBM Domino database; the listing is a view read with
     `?ReadViewEntries&ExpandView&Count=N`. `kind_column`, `title_column` and `number_column` name
     the view columns; only entries whose kind is in `kinds` are kept. Detail pages are read at
     `<database>/0/<unid>?OpenDocument`.
3. Choose `sections` or `kinds` so that only rules for residents are collected.
4. `hosts` lists every host the collector may contact for that kommun; `region_code` must be the
   first two digits of the kommun code.
5. Add a trimmed listing (and detail page) fixture and a test, then run a small sample with
   `--kommun <code> --limit 5` and the audit.

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing, list file or robots.txt could not be read, or the state file is corrupt
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

These apply to `sfs` and `case-law`.

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
