# lagar collector

Collects Swedish statutes (SFS) from Riksdagen open data into `corpus/` Markdown files,
records a SHA-256 manifest of the authoritative SFS PDFs, adds each statute's amendment
register from SFSR, writes a metadata-only amendment history for git, collects the published case
law of the Swedish courts, collects EU acts in Swedish from the Publications Office Cellar,
collects agency regulations (AFS, FFFS, TSFS, MIGRFS and others) and collects municipal regulations from
the kommuner's own författningssamlingar.
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

## PDF text

`lagar/pdftext.py` is the one place that reads text out of an official PDF; every collector that
needs it calls `pdftext.extract(data)`. It runs poppler's `pdftotext` on a temporary copy of the
bytes, so the collector itself stays stdlib-only. Install poppler-utils (`sudo apt-get install
poppler-utils`, `brew install poppler`); the collector and sync workflows install it on the runner.

- `extract` returns `PdfText(text, pages, text_pages, gap)`. Pages are split by form feeds; a page
  with fewer than 40 letters and digits has no text layer.
- When less than half of the pages carry text, `gap` is `"no text layer (scanned PDF)"`; when
  less than half of the visible characters are letters or digits (fonts without a Unicode map),
  `gap` is `"text layer is not readable ..."`. Callers record the gap and keep the PDF link and
  SHA-256; they never guess or OCR the text.
- `paragraphs(text)` reflows the text into paragraphs: a new one starts after a blank line, before
  `N §`, `N kap.`, `1.` or `a)`, and after a short line followed by a capital or digit; other lines
  are joined, line-break hyphens removed (not before "och", "eller" and similar), lines holding
  only a page number or a rule dropped.
- A missing tool, a timeout or a file `pdftotext` cannot open raises `pdftext.PdfTextError`.
- Tests that run the tool skip when it is not installed, unless `LAGAR_REQUIRE_PDFTOTEXT=1`
  (set in CI).

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
    [--refresh] [--changed-since DATE[TIME]] [--limit N] [--cache sources/cache/eu [--offline]] \
    [--corpus corpus] [--manifest sources/eu-manifest.json] \
    [--state collector/data/eu-state.json] [--rate SECONDS] [--report FILE]
python3 -I collector/collect.py eu --celex 32016R0679[,32022L2555 ...] [options]
```

- Metadata: one SPARQL query per act to `https://publications.europa.eu/webapi/rdf/sparql`
  (date of document, entry-into-force dates and their type, end of validity, ELI, adopting institutions, Swedish
  title and manifestation types, amending acts and consolidated versions).
- Text: `https://publications.europa.eu/resource/celex/<CELEX>` with `Accept-Language: swe`
  and `Accept: application/xhtml+xml` (or `text/html` for older acts that only have the old
  EUR-Lex HTML) answers 303 with the Swedish manifestation. It is converted to Markdown with
  `html.parser`: divisions (KAPITEL, AVDELNING, AVSNITT, BILAGA) as `##`, articles as `###`,
  article and chapter titles in bold, point labels kept with their text. Two or more adjacent
  table rows of several cells (correlation tables, amendment lists, annex tables) become a
  Markdown (GFM) table with the first row as header; a lone row, or a table nested in another
  table's cell, stays on one line with cells separated by ` | `. The OJ page header and the
  `►M1 … ◄` / `▼B` markers of consolidated texts are dropped. Text cleanup (invisible
  characters, whitespace), `#` escaping and the table renderer are shared with the case-law
  converter in `lagar/htmlmd.py`; the EU-specific structure (OJ classes, point labels,
  divisions) stays in `lagar/eu.py`, since the generic converter has no notion of it.
- **eur-lex.europa.eu is never contacted.** Its front end answers automated clients with a
  WAF challenge. Every request, and every redirect, must stay on `publications.europa.eu` or
  `op.europa.eu` (where its robots.txt lives); redirects are followed over https only.
- Acts without a Swedish expression, or with Swedish only as PDF or print (REACH, for
  example), are recorded as gaps in the state file and in the manifest's `gaps`; nothing is
  translated. `--consolidated` also collects each act's latest consolidated version that
  applies today (CELEX `0…-YYYYMMDD`) and removes older consolidated versions of that act.
  The curated list is collected this way, so every act has its Official Journal text
  (`authoritative: true`, where Swedish XHTML or HTML exists) and its latest consolidated
  version (`authoritative: false`).
- Frontmatter: `id` `eu-<celex lowercased>`, `number` in the Swedish citation form taken from
  the Swedish title when it agrees with the CELEX number (else rebuilt from it: `(EU) 2016/679`,
  `(EG) nr 1907/2006`, `95/46/EG`), `celex`, `issued` (date of document; for a consolidated
  version, the base act's), `in_force` (the act's own entry into force: the
  `resource_legal_date_entry-into-force` annotated `type_of_date` EV; dates annotated MA or
  MA/PART are when the act or single provisions apply and never count; without an EV date,
  the earliest unannotated date, as for consolidated versions, else `null`), `repealed` (end of
  validity unless open-ended), `amended_by` (CELEX numbers of amending acts), `amended_through`,
  `eli`, `issuer`
  (adopting institutions in Swedish), `source` (the manifestation URL), `source_sha256`.
  `authoritative` is true for the Official Journal text, false for consolidated versions.
- Amendments of a consolidated version come from Cellar's
  `act_consolidated_consolidates_resource_legal`, read over every consolidated version of the
  base act up to this one (each version lists only what it adds). `amended_by` lists those
  amending acts and `amended_through` the latest of them by date of document; the base act,
  earlier consolidated versions and corrigenda (`…R(01)`) are left out. The Official Journal
  text has no amendment applied, so its `amended_through` stays `null`; its `amended_by` lists
  the acts that amend it (`resource_legal_amends_resource_legal`).
- The committed manifest `sources/eu-manifest.json` lists, per act, `celex`, `id`, `url`,
  `content_type`, `bytes`, `sha256` and `retrieved_at` (kept while the bytes are unchanged),
  plus the gaps. `--cache DIR` keeps, per act, the SPARQL answer (`<CELEX>.sparql.json`), the
  text (`<CELEX>.<format>`) and its URL and content type (`<CELEX>.source.json`); use the
  git-ignored `sources/cache/eu`. `--offline` then reconverts from the cache without any
  request, which is how a converter change is applied and compared.
- Resume: the state file (git-ignored) keeps `done` (CELEX to SHA-256), `failed`, `gaps` and
  `blocked`. Collected acts are skipped unless `--refresh`; a refresh rewrites a document only
  when its frontmatter (apart from `fetched_at`) or its converted text changed.
- `--rate` defaults to, and may not go below, 1 s. An HTTP 403, a long `Retry-After` or a
  robots.txt disallow stops the run (exit code 2).
- `--report` writes `{"written": [...], "unchanged": [...], "skipped": n, "gaps": [...],
  "failed": [...], "blocked": bool, "latest_modified": ..., "retry_from": ...}`.
- Incremental runs: `--changed-since` takes a date or a UTC date-time and asks Cellar, in one
  SPARQL query, which listed acts changed after it: the work itself, any of its consolidated
  versions or an act amending it (`cmr:lastModificationDate`). Only those are collected again
  (as with `--refresh`), with their latest consolidated version when `--consolidated` is given.
  `latest_modified` in the report is the newest change seen, and `retry_from` is one
  millisecond before the oldest change that could not be collected (failure, block or
  `--limit`), so `retry_from // latest_modified` is a safe next marker.
- Cellar also has an ingestion notification feed
  (`/webapi/notification/ingestion?startDate=…&type=UPDATE`, RSS). It covers every ingestion
  in Cellar, keyed by Cellar id rather than CELEX, at about 1.3 MB per page and several pages
  per day, so following it for a list of 43 acts costs far more than the one SPARQL query
  above. It is not used.

### Daily sync

The `Sync EU` workflow (`.github/workflows/sync-eu.yml`) mirrors `Sync SFS`: every day it runs
`collect.py eu --list collector/data/eu-acts.json --consolidated --changed-since <marker>` and
puts any corpus change into one pull request on `data/eu-sync`. The marker,
`collector/data/eu-sync.json` (`{"changed_since": "YYYY-MM-DDTHH:MM:SS.mmmZ"}`), only moves in
the commit that carries the documents, so a failed run never skips a change. A day without
changes costs one SPARQL query; Cellar touches the metadata of the curated acts often (about
half of them in two months), but a touched act whose text and frontmatter are unchanged is
not rewritten and opens no pull request. Run it by hand with
`gh workflow run sync-eu.yml [-f since=YYYY-MM-DD]`; an earlier `since` only widens the window.

The curated list `collector/data/eu-acts.json` holds the acts the app highlights (data
protection, digital, consumer, labour, environment, private international law). A wider
in-force sweep is not implemented yet. Reuse is free with acknowledgement of the source
(Commission Decision 2011/833/EU).

## EU case law (Cellar)

```sh
python3 -I collector/collect.py eu-case-law --list collector/data/eu-acts.json \
    [--refresh] [--changed-since DATE[TIME]] [--limit N] [--cache DIR] [--report FILE]
python3 -I collector/collect.py eu-case-law --celex 62014CJ0362[,62012CJ0293 ...] [options]
```

The collection is bounded to judgments of the Court of Justice (CELEX type `CJ`) and the
General Court (`TJ`) that Cellar records as interpreting an act of the curated list
(`cdm:case-law_interpretes_resource_legal`). One SPARQL query lists them with their newest
Cellar modification; per judgment one query reads the metadata (date, ECLI, language of the
case, joined cases, interpreted acts, Swedish title and manifestations) and content
negotiation on `/resource/celex/<CELEX>` with `Accept-Language: swe` returns the Swedish
XHTML or HTML, converted with the EU act converter. The same host rules apply as for EU acts:
only publications.europa.eu and op.europa.eu, robots.txt checked, at least 1 s between
requests, eur-lex.europa.eu refused even as a redirect target.

Documents are `eu_judgment` in layer `eu`, under `corpus/eu/judgments/`, with the case
number as `number` (`C-362/14`, `T-12/19`, `26/62` before 1989), `court` `CJ` or `TJ`, the
judgment's `ecli` and `celex`. The body starts with the case numbers (joined cases
included), the ECLI and the interpreted acts. Only the language of the case is authentic,
so `authoritative` is true only for cases conducted in Swedish. A judgment without a Swedish
XHTML or HTML expression is a gap in the manifest `sources/eu-case-law-manifest.json` (size
and SHA-256 of every source); nothing is translated. Orders (`CO`), Advocate General
opinions (`CC`) and judgments that interpret no curated act are not collected.

The daily `Sync EU` workflow runs `eu-case-law --list collector/data/eu-acts.json
--changed-since <marker>` after the acts, with its own marker
`collector/data/eu-case-law-sync.json`, so new judgments and Cellar corrections arrive in
the same pull request as the acts.

## Treaties (SÖ)

```sh
python3 -I collector/collect.py so [--from-year YYYY] [--to-year YYYY] [--text-from-year 2010] \
    [--changed-since YYYY-MM-DD] [--url URL ...] [--refresh] [--limit N] [--report FILE]
```

Sveriges internationella överenskommelser (SÖ) publishes every international
agreement binding Sweden. Regeringen.se has one page per agreement under
`/rattsliga-dokument/sveriges-internationella-overenskommelser/`; the collector finds
them in the site's sitemap (one request, with each page's last modification), reads
robots.txt once and honours it for every URL, and fetches at most one page a second.
Each page gives the title, the place and date of signature (`issued`), the SÖ number,
the ministry, a note on the government's decision and the entry into force
(`in_force`, when the note states it) and the PDF links. Pages without an SÖ number,
such as declarations of intent published in the same section, are skipped. Some
treaties are published again on a second page (often in a bulk folder such as
`1994/01/` or `2012/12/`, with extra PDFs), and a few old pages carry a number another
page already uses; the page whose URL sorts first keeps the number and the others are
recorded in the state file as duplicates.

Documents are `treaty` in layer `sfs`, under `corpus/sfs/treaties/`, with ids such as
`so-2023-3`. The text is only published as PDF: for SÖ years from `--text-from-year`
(default 2010) the PDFs are downloaded and their text extracted with
`collector/lagar/pdftext.py`; size, SHA-256, page count and the extraction result go
into `sources/so-pdf-manifest.json`, and the bytes are not kept. Older treaties, and
scanned PDFs, keep the page metadata and the PDF link only. Many treaties are printed
in Swedish and one or more other languages side by side; the extracted text keeps
every language, as printed. `authoritative` stays false: the text is not tied to a
verified snapshot of the print.

The weekly `Sync SÖ` workflow (`.github/workflows/sync-so.yml`) runs
`collect.py so --changed-since <15 days ago>`, so new treaties and updated pages land
in one pull request on `data/so-sync`.

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
  (`sammanfattning`, the report's headline); when the summary holds several paragraphs separated
  by `-----` rules, the title is the first and the others go to a `## Sammanfattning` section.
  `issued` is the decision date, `court` the court code, `issuer` the court name, `ecli` the ECLI
  when it has the standard form. `source` is
  `/api/v1/publiceringar/{id}` and `source_sha256` hashes the publication as the API serialises it
  (sorted keys, compact UTF-8 JSON), which is byte for byte the response of that URL.
- Body: a facts block (court, decision date, case numbers, all references, name, ECLI), then
  the remaining summary paragraphs, then sections for Lagrum (with SFS numbers), Nyckelord,
  Rättsområden, Förarbeten, Litteratur, Hänvisningar and Europarättsliga avgöranden when present,
  then the text (`innehall`, HTML
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
  "latest_published": "...", "next_since": "YYYY-MM-DD"}`. `next_since` is the day of the newest
  publication seen, or `--since` unchanged when the run was limited, filtered by court or decision
  date, blocked, or saw nothing newer; the scheduled sync stores it as its marker.
- Lagrum references stay plain text in the body (`22 § förvaltningslagen (1986:223)`, or
  `... (SFS 1986:223)` when the reference lacks the number). The app's reader turns these citation
  forms into links to the SFS documents the API publishes, so no extra frontmatter field is needed.
- The site has no robots.txt (HTTP 404); one is honoured if it appears. An HTTP 403 stops the run
  (exit code 2). Entries may shift between pages while the courts publish; a rerun picks up any miss.

### Scheduled case-law sync

`.github/workflows/sync-case-law.yml` mirrors the SFS sync: daily, and on manual dispatch with an
optional earlier `since` (`gh workflow run sync-case-law.yml [-f since=YYYY-MM-DD]`). It starts
from `main`, or from the `data/case-law-sync` branch while a sync pull request is open, and runs
`case-law --since <marker>` with the day in `collector/data/case-law-sync.json`
(`{"published_since": "YYYY-MM-DD"}`). When the corpus changed it writes the report's
`next_since` to the marker, regenerates the audit and progress files, adds one `data(case-law):`
commit to `data/case-law-sync` and opens a pull request (labels `type: data`, `area: corpus`,
assigned to the owner) if none is open. The marker only moves inside that commit, so a failed or
abandoned run never skips publications. The job summary lists what was written, excluded and
failed.

## Agency regulations

The `agency` command collects agency regulations (myndighetsföreskrifter) from each agency's own
register. There is no central database; lagrummet.se lists the series and links to the
registers. Regulations carry no copyright (9 § upphovsrättslagen).

```
python3 -I collector/collect.py agency --series AFS|FFFS|TSFS|<listed series> [--series ...] [--year YYYY ...] \
    [--number 'AFS 2023:1' ...] [--limit N] [--refresh] [--rate SECONDS] \
    [--state collector/data/agency-state.json] [--manifest sources/agency-pdf-manifest.json] \
    [--corpus corpus] [--report FILE]
```

Each series has a small adapter in `collector/lagar/agency.py` that lists the regulations
(`listing_urls`, `parse_listing`) and parses one detail page (`parse_detail`); the shared run
loop does robots.txt, rate limiting, state, PDF hashing and writing. Adding a series means
adding an adapter and registering it in `ADAPTERS`.

Series whose regulation page is just a list of links to the PDFs need no code: add them to
`collector/data/agency-series.json` (`issuer`, `listing_urls`, and `prefix` when the number is
written in more than one way, e.g. `SGU[- ]?FS`; `exclude` overrides the default filter that
skips guidance, preparatory work and register PDFs; `separator` when the number is written
`SKSFS 2011 7`; `documents` when PDF links do not end in `.pdf`; `base_href` when the site files
every amendment under its base regulation's folder, with the base's year and ordinal as groups;
`detail_pages: true` when the listing links to one page per regulation that holds its PDF links).
`ListedAdapter` classifies each link by its
label, then its file name: a base regulation, an amending or repealing regulation (`om ändring
i ... (XFS 2015:2)`, kept only in the base regulation's `amended_by`), or a consolidated version
or reprint (linked from the base regulation). Every run rebuilds the series from the listing;
PDFs already in the manifest are not downloaded again unless `--refresh`. An adapter can also name further listing pages (`more_pages`) or fetch its listing itself (`fetch_listing`, e.g. a POSTed search form through `PoliteClient.post`). The document's
`source` is the regulation's own PDF and `source_sha256` its hash.

Series published as a plain page of links use the configurable adapters in
`collector/lagar/agency_generic.py`: `PdfListAdapter` when the listing links straight to the
PDFs (MIGRFS, KAMFS, KFMFS, KFS, KRFS, MEMYFS, IAFFS, BFNAR, CSNFS, IMYFS, LMFS, MTFS, LIVSFS, MYHFS, KBVFS, FFS) and `DetailPageAdapter` when it links to one
HTML page per regulation (ELSÄK-FS, MCFFS, MDFFS, KIFS, AGVFS, KOVFS, HVMFS, EIFS); `SitemapAdapter`
finds the regulation pages in the site's XML sitemap when the register needs JavaScript (NFS, KVFS, DVFS; `path_pattern` keeps one page per base
regulation).
A detail page's HTML text is kept when the series sets `text_nodes` (MDFFS). AFFS reads the
list from the Sitevision page state and FKFS the JSON register of Försäkringskassan's
lagrummet; both have their own small adapters in the same module.
A series there is a subclass that sets the listing URLs and, where
needed, the list item element. The number comes from either end of the item's text, else from
the PDF's file name; amending and repealing regulations are recognised by their titles ("om
ändring i", "om upphävande av") and listed in the `amended_by` of the base regulation they
name. For PDF entries (`detail = False`) the PDF is the document: `source` is its URL and
`source_sha256` its hash. A `PdfListAdapter` can also read a list item as a heading and what
follows it (`group_by = "h3"`: LMFS, MTFS) or a link and the text after it (`group_by = "a"`:
IMYFS), take the number from one cell of a table row (`number_node`: BFNAR), leave out the items
under a heading such as "Upphävda föreskrifter" (`skip_section`) and mark the PDFs under a heading
such as "Fulltext" (`consolidated_section`: CSNFS) or behind a "konsoliderad version" link as
consolidated versions. Companion documents (vägledning, konsekvensutredning, rättelseblad) are
left out. A table row that links through `data-href` instead of a link is read too (KBVFS).
`pdf_title = True` takes the title from the PDF when the listing only gives a short name
(BFNAR). FFS reads its four lists from Försvarsmakten's content API
(`/api/episerver/v3.0/content/<page>?expand=PDFFilesArea`), which only gives file names; the
title, and whether a regulation is an amendment, come from the PDF. When the listing only named
the number and the PDF title shows an amendment, the regulation is excluded.
HSLF-FS, the series the health and social-care agencies share, comes from the JSON behind
kunskapsguiden.se's list (designation, heading, agency, link). Its regulations sit on each
agency's own site, so the adapter sets `multi_host = True` and the run reads robots.txt per host;
the agency becomes the document's `issuer`. A link straight to a PDF makes the PDF the document,
and on a page that lists many regulations (TLV) only the PDFs naming the number are kept.
Läkemedelsverket's regulations are not collected: its pages need JavaScript and its robots.txt
disallows PDFs. Predecessor series on the same list (SOSFS, FoHMFS and others) are not collected.

Adapters whose site publishes no HTML text (`has_text = False`) get their text from a PDF:
the consolidated version when one is linked, else the regulation's own PDF, read with
`collector/lagar/pdftext.py` from the same download that hashes it and turned into Markdown by
`collector/lagar/agency_text.py` (masthead dropped, section signs in bold). The masthead also
gives the title when the listing only names the number, and the decision, publication and
entry-into-force dates when the listing has none. A scanned PDF is noted in the body. The run
stops when `pdftotext` (poppler-utils) is missing; `--no-pdf-text` skips the step.

| series | listing | detail | text |
| --- | --- | --- | --- |
| AFS (Arbetsmiljöverket) | `https://www.av.se/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/`, "Gällande grundföreskrifter" plus the amending regulations in force | `.../foreskrifter/afs-20231/` | HTML, the latest consolidated version |
| FFFS (Finansinspektionen) | `https://www.fi.se/sv/vara-register/fffs/forteckning-fffs/` (all regulations in force, newest first) | `.../sok-fffs/<year>/<yearnumber>/` | PDF only |
| TSFS (Transportstyrelsen) | `.../ts-foreskrifter-i-nummerordning/<year>/` (in force and repealed) | `.../<year>/details?RuleNumber=<year>:<n>&ruleprefix=TSFS` | PDF only |
| ÅFS (Åklagarmyndigheten) | `https://www.aklagare.se/om-oss/dokument/forfattningssamling` (cards with dates and tags) | none | PDF only |
| STAFS (Swedac) | `https://regelverk.swedac.se/foreskrifter.json` (in force and repealed) | `.../<slug>.md` (consolidated where there is one) | Markdown |
| PRVFS (PRV) | division A1, base regulations in force | none | PDF only |
| PMFS, RPSFS (Polismyndigheten) | `https://polisen.se/lagar-och-regler/polismyndighetens-forfattningssamling/<page>/` | none | PDF only |
| SCB-FS (SCB) | table of regulations on reporting duties | `/link/<id>.aspx` | HTML |
| STEMFS (Energimyndigheten) | document archive, category Föreskrifter, 40 a page (crawl delay 10 s) | none | PDF only |
| RFS (Riksdagsförvaltningen) | `https://data.riksdagen.se/dokumentlista/?doktyp=rfs&utformat=json` | `https://data.riksdagen.se/dokument/<dok_id>.html` | HTML (Fulltext) |
| RA-FS (Riksarkivet) | `https://foreskrifter.riksarkivet.se/api/rafs/sok` (JSON, in force and repealed) | none | PDF only |
| SKOLFS (Skolverket) | `https://skolfs.skolverket.se/api/statute` (JSON, paged) | `.../api/document/<number>/ascending` (JSON) | PDF only |
| SJÖFS (Sjöfartsverket) | `.../lagrum/systematisk-forteckning-n/<subject>/` (21 subject pages) | none | PDF only |
| TRVFS (Trafikverket) | `https://trvfs.ea.trafikverket.se/TRVFS/Home/SearchInDocCollection` (POST per year) | `.../Home/DocumentHistory/<year>-<n>` | PDF only |

- Only base regulations (grundförfattningar) are stored, in `corpus/agency/regulations/`.
  Amending regulations are counted as `excluded` and appear in the base regulation's
  `amended_by` and in its body. FFFS uses the register's own type; TSFS uses the title
  (`Föreskrifter om ändring/ändringar/upphävande ...`), and a TSFS page that shows another
  regulation which lists the requested number as an amendment is excluded too. FI classes its
  repealing regulations (`Föreskrifter om upphävande av ...`) as base regulations; they are kept.
  AFS takes the base regulations from "Gällande grundföreskrifter"; the repealing regulations the
  overview lists under "Gällande ändringsföreskrifter med upphävanden" are excluded. The TSFS
  year listings also hold repealed regulations: their base regulations are stored with
  `repealed` set from the listing's "Upphävd" badge.
- Mapping: `id` is the slug of the number (`afs-2023-1`, `hslf-fs-2016-40`), `number` the
  series-prefixed number (`AFS 2023:1`), `issuer` the agency, `language: sv`, `eli: null`,
  `authoritative: false` (the printed series is authoritative). AFS: `issued` is "Beslutad",
  `in_force` "Träder i kraft" (both only on pages of unamended regulations) and `amended_through`
  the "Ändringar är införda till och med" note of consolidated pages. FFFS: `in_force` is
  "Gäller från". TSFS: `in_force` and `repealed` come from the year listing and the base PDF
  entry. `source` is the detail page and `source_sha256` hashes it as served.
- Body: a facts block (series, issuer, dates, version), the agency's own summary when there is
  one, the amending regulations (with entry into force and scope where published), links to the
  PDFs, then the text. AFS text is converted from the page's HTML: section signs in bold,
  "Allmänna råd" captions, lettered and roman list markers, tables flattened to one row per line
  and footnotes collected under `## Fotnoter`. FFFS and TSFS publish the text only as PDF;
  their bodies say so and link the official PDFs. PDF text is not extracted.
- PDFs listed on a detail page are downloaded once to record `url`, `bytes`, `sha256`,
  `content_type` and `retrieved_at` in the committed manifest `sources/agency-pdf-manifest.json`
  (keyed by regulation number). A response that is not a PDF fails the regulation. The bytes are
  never stored. AFS PDFs are not requested: the text comes from HTML, and Arbetsmiljöverket's
  robots.txt disallows the folder with the original PDFs
  (`/globalassets/filer/publikationer/foreskrifter/ursprungs/`).
- robots.txt is read per host before anything else and checked for every URL: a disallowed
  listing stops the run as blocked (exit code 2), a disallowed detail page fails that
  regulation and a disallowed PDF is listed in the manifest without a hash. A `Crawl-delay`
  raises the interval. `--rate` defaults to, and may not go below, 1 s. An HTTP 403 stops the run.
- `--year` keeps regulations numbered in those years; for TSFS it also picks the year listings
  to read (without it, every year on the index). `--number` picks single regulations. `--limit`
  stops after N written documents per series (unchanged and skipped ones do not count).
- State (git-ignored) is `{"done": {number: page sha256}, "failed": {number: error},
  "blocked": null|msg}`. Done regulations are skipped while their file exists; `--refresh`
  refetches them and hashes their PDFs again (a consolidated PDF can change behind the same
  URL). A document whose body and frontmatter, apart from `fetched_at` and `source_sha256`, are
  unchanged is left untouched, so page chrome changes do not churn the corpus.
- `--report` writes `{"written": [...], "unchanged": n, "skipped": n, "excluded": n, "pdfs": n,
  "failed": [...], "blocked": bool}`.

Not yet collected: Boverket (BFS) has an official API with full text from 2024 on, which probably
needs a subscription key from `api-portal.boverket.se` (owner decision). Skatteverket's
`www4.skatteverket.se` rejected the robots.txt request (WAF), so access must be confirmed first.
Arbetsmiljöverket's regulation API is in a closed evaluation and needs a key; the public HTML
pages are used instead.

The weekly `Sync agency regulations` workflow (`.github/workflows/sync-agency.yml`) runs the
collector for every series in `ADAPTERS`, so a new adapter or a new entry in
`collector/data/agency-series.json` joins the sync without editing the workflow. Series read by
year (TSFS) are limited to the current and previous year. Changes land as one pull request on
`data/agency-sync` with the regenerated progress files and agencies log; the run summary lists
written, unchanged, excluded, failed and blocked per series. Run it by hand with
`gh workflow run sync-agency.yml [-f series='AFS SKSFS']`.

## County regulations

The `county` command collects one county's regulations (länets författningssamling, series
`01FS`–`25FS`) from the shared site of the county administrative boards, `www.lansstyrelsen.se`.
There is no API or open data set; the texts are free of copyright (9 § upphovsrättslagen).

```
python3 -I collector/collect.py county --county CODE [--from-year YYYY] [--to-year YYYY] \
    [--newest-first] [--limit N] [--no-pdf] [--no-text] [--refresh-pdf] [--landing-url URL] \
    [--rate SECONDS] \
    [--config collector/data/counties.json] [--state collector/data/county-state.json] \
    [--manifest sources/county-pdf-manifest.json] [--corpus corpus] [--report FILE]
```

- `--county` (alias `--region`) is the county code, `01` (Stockholm) to `25` (Norrbotten); `01FS`
  is accepted too. The run reads `robots.txt` first, then the county's landing page. Years and
  numbers are walked oldest first unless `--newest-first` is given; `--from-year`/`--to-year`
  limit the years.
- `collector/data/counties.json` gives each county's landing page and layout (the page paths differ
  per county: `om-lansstyrelsen-<county>`, `om-lansstyrelsen-i-<county>s-lan`, `forfattningar.html`
  and others). `--landing-url` overrides the landing page for one run. Two layouts exist:
  - `pages` (Stockholm, Halland, Gävleborg): the landing page links one index page per year
    (`.../forfattningar-<year>.html`), which links each regulation's detail page with the text as
    HTML.
  - `files` (the other 18 counties): the landing page lists only the printed PDFs, as plain
    `/download/` links in the text, as files in Sitevision's file-share module (its initial state
    is embedded in the page), or as one file-share folder per year. A year folder is listed by the
    module's own JSON endpoint (`/appresource/<page id>/<module id>/files?folderId=<id>`, the request
    the browser makes when the folder is opened); only folders of the requested years are read.
    The number comes from the link text or else the file name, with the county's
    `number_patterns` (regular expressions with groups `year`, `n` and optionally `code`; the
    default reads `04FS 2026-1`, `22 FS 2026-1`, `18FS2025 1`, `FS 2026-01`). A number in another
    county's series is skipped. A link without a number in its text or file name is downloaded and
    gets the first number of the county's series printed in the top of its PDF text (a link already
    in the manifest keeps its number without a download). Links that still have no number
    (registers, information sheets, scanned files) are not collected and are listed in the report
    as `unnumbered` when they belong to a requested year (every one when no year is given).
- Each URL is checked against `robots.txt` before it is requested; a disallowed URL or an HTTP 403
  stops the run (exit code 2). `--rate` must be at least 1 second (the default).
- Mapping (`county_regulation`, `layer: region`, `corpus/region/county-regulations/`): `number` is the
  printed number with the leading zeros of the ordinal dropped (`01FS 2026:01` -> `01FS 2026:1`),
  `id` its slug (`01fs-2026-1`). A number outside the requested county's series fails. `issuer` is
  "Länsstyrelsen i <county>", `region_code` the county code; `repealed` and the amendment fields
  stay empty.
  - `pages`: `title` is the page's ingress without the final period, `issued` the decision date
    ("Beslutat den ...") or, when the page has none, the publication date ("Utkom från trycket den
    ..."). `in_force` is set only when the text names exactly one date in "träder i kraft den ...".
    `source` is the detail page and `source_sha256` hashes its heading, ingress and text fragments
    (the full page carries a per-request script nonce, so it is not hashed whole).
  - `files`: `title` is the title printed in the PDF (an early paragraph ending in `;` that names a
    regulation or decision) when its text was read; otherwise the link text without the number,
    `.pdf` and an "UPPHÄVD" mark (plus the county's `title_strip` patterns); when nothing is left,
    the paragraph following a plain link is used (Dalarna), or else the number itself. `issued` is
    the decision date of that paragraph when there is one, otherwise the "beslutade den ..." date of
    the PDF text; `in_force` comes from the PDF text like for `pages`. `source` is the PDF and
    `source_sha256` its SHA-256 (with `--no-pdf`, a hash of the link URLs and texts). Files sharing
    a number (a regulation and its map) form one document.
- Body: a facts block (number, publication and decision dates, entry into force, issuer; for
  `files` also the landing page), the text of the detail page converted to Markdown (lists and
  nested lists kept; links keep their text), then `## Tryckt version` with links to the printed
  PDF. Regulations published only as PDF (all of the `files` layout, and detail pages without
  text) get the PDF's text instead, read with `lagar/pdftext.py` and reflowed into paragraphs;
  with several readable files (a regulation and its appendix) each gets a heading. A PDF without
  a readable text layer (scanned) is a gap: the body says the text is only in the PDF and nothing
  is guessed. A regulation the county marks "UPPHÄVD" gets a note saying so. `pdftotext`
  (poppler-utils) must be installed unless `--no-text` (or `--no-pdf`) is given.
- PDFs: on detail pages, a paragraph made only of PDF links is the regulation's own printed
  version; PDF links in running text point at other regulations and are not followed. Each own PDF
  is downloaded once (where `robots.txt` allows) to record its size and SHA-256 in the committed
  manifest `sources/county-pdf-manifest.json` (entries `number`, `detail_url` (the landing page for
  `files`), `published`, `files[]` with `url`, `bytes`, `sha256`, `content_type`, `retrieved_at`
  and, for files whose text was read, `text`: `extracted`, a gap reason such as `no text layer
  (scanned PDF)`, or `unreadable PDF`); the bytes are not kept. `--no-pdf` records the links with
  null hashes; a later run without it fills them. A PDF whose hash and `text` are in the manifest
  is not downloaded again while its corpus file exists, so the body is left as it is; `--refresh-pdf`
  downloads and reads every PDF again.
- As for case law, a text containing a personal identity number is recorded as failed.
- State (git-ignored) is `{"done": {number: source_sha256}, "failed": {number: error}, "blocked":
  null|msg}`; a regulation is skipped without a request when it is done and its file exists. A
  document whose frontmatter (apart from `fetched_at`) and body are unchanged is left untouched.
- `--limit` stops after N written documents (unchanged ones do not count). `--report` writes
  `{"written": [...], "unchanged": n, "skipped": n, "failed": [...], "unnumbered": [...],
  "blocked": bool}`.

## Municipal regulations (kommunala författningssamlingar)

Each kommun publishes its own författningssamling on its own website; there is no national
dataset. `municipal` reads the kommuner listed in `collector/data/municipalities.json`.

```
python3 -I collector/collect.py municipal --kommun 0180 [--kommun 1480 ...] [--limit N] \
    [--refresh] [--report FILE] [--rate SECONDS] [--config collector/data/municipalities.json] \
    [--state collector/data/municipal-state.json] [--manifest sources/municipal-manifest.json]
python3 -I collector/collect.py municipal --all [--limit N]
python3 -I collector/collect.py municipal --kommun 0120 --dry-run
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
  "gaps": {id: reason}, "blocked": {code: reason}}`. A document is skipped when it is done (or, for
  `html_index`, already in the manifest at the same URL) and its file exists, unless `--refresh`; a refreshed document whose frontmatter (apart from `fetched_at`)
  and body are unchanged is left untouched.
- `--limit` stops after N written documents per kommun. `--report` writes `{"written": [...],
  "unchanged": [...], "skipped": n, "gaps": [...], "failed": [...], "blocked": {code: reason}}`.
- An HTTP 403, an unreadable robots.txt or listing, or a redirect off the configured hosts blocks
  that kommun (exit code 2); the other kommuner still run.
- The weekly `Sync municipal regulations` workflow (`.github/workflows/sync-municipal.yml`) runs
  `municipal --kommun <code>` for every kommun in the config, one at a time so that one kommun's
  failure does not stop the others, and opens one pull request on `data/municipal-sync` with the
  corpus, the manifest and the regenerated reports. The state is not committed; the manifest keeps
  the weekly run from downloading PDFs it already has. Run it by hand with
  `gh workflow run sync-municipal.yml [-f kommun="0114 0115"]`. A kommun added to the config joins
  the next run.

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
   - `"preset": "sitevision"`: most kommuner run Sitevision and publish the collection as one flat
     file list (`/download/18.<node id>/<timestamp>/<name>.pdf`). The preset fills in
     `strategy` (`html_index`), `link_pattern`, `number` (the file's node id, which stays the same
     when the file is replaced), `title_strip` (the ".pdf" and "Pdf, 290 kB." suffixes), `follow`
     and `embedded_json`. The entry's own keys win over the preset's.
   - `embedded_json` (`html_index`): Sitevision file-share and file-list modules often render their
     files in the browser from `AppRegistry.registerInitialState(...)` JSON, so the static HTML has
     no anchors for them. With this flag, every object in that JSON with a `url` (or `uri`) under
     `/download/` and a `title` (or `name`) counts as a link under the heading before the script.
   - `follow` (regex, `html_index`): links on a listing whose absolute URL matches are read as
     further listing pages (pagination), up to 100 pages, skipping those robots.txt disallows. The
     Sitevision preset follows its file list's `?lp-page=N` links.
   - `html_pages`: kommuner that publish each rule as its own web page (Oskarshamn's taxor are page
     text, with no PDF). The listing is read as for `html_index`, with `link_pattern` matching the
     rule pages. Each page is fetched: when it links a document matching `document_pattern`
     (for example `\\.pdf$`), that PDF is the source and the page text goes into the body as the
     kommun's note; otherwise the page text itself is the document. The text is the page's `<main>`
     element (or the element whose id is `content_id`) converted with `htmlmd`, without print,
     feedback and "senast granskad" lines; `source` is the page URL and `source_sha256` hashes the
     converted text, so markup changes alone do not count as a new version. A page with less than
     40 characters of text outside its headings is a failure (an empty page, not a rule). The text
     starts at the content's first `<h1>`, so menus and breadcrumbs placed before it inside `<main>`
     are left out. A listing link that answers with a PDF is taken as the document itself.
   - `page_titles` (`html_pages`): links without a usable title are kept, and each rule's title is
     its page's `<h1>`; the title filter is applied to that title after the page is read (a page
     that fails it is skipped). Needed when the listing is a sitemap.
   - Sitemap listings: a listing that is an XML sitemap (`<urlset>`) yields its URLs as untitled
     links; a sitemap index (`<sitemapindex>`) yields nothing itself and its child sitemaps are
     read when they match `follow`.
   - `row_titles` (`html_index`, `html_pages`): for links inside a table row, the title is the text
     of the row's other cells (Torsås's links all read "Ladda ner").
   - `json_list`: the listing is a JSON document list from the platform's own API, such as an
     Evolution DocumentWeb folder (`/api/folders/<folder id>`) or a WordPress File Download
     category (`/wp-admin/admin-ajax.php?action=wpfd&task=files.display&id=<category>`). `items`
     is the dotted path to the list (`documents`, `files`; empty when the document is the list),
     `title_field` and `number_field` name the item fields for the title and number, and
     `url_template` builds the document's link from the item's fields (`/api/download/{id}/{folderId}`,
     `{linkdownload}`), resolved against the listing URL. `link_pattern`, when set, filters the
     built links; `resident_filter` and `title_include`/`title_exclude` filter the titles. An item
     with no number or a template field it lacks is reported as a problem.
3. Choose `sections` or `kinds` so that only rules for residents are collected. Where the list mixes
   rules and internal documents with no headings to tell them apart, `"resident_filter": true`
   keeps a title only when it names a rule for residents (föreskrifter, taxor, avgifter, avfall,
   renhållning, hälsoskydd, naturreservat, hamnordning, torghandel, ABVA and the like) and drops
   titles of internal documents (reglementen, arbetsordningar, delegationsordningar, planer,
   program, policyer, riktlinjer and the like). `title_include` and `title_exclude` (regex lists)
   replace the built-in lists for a kommun.
4. `--dry-run` prints each listed document (`id`, title, URL) without fetching documents or writing
   anything; use it to check a new entry.
5. `hosts` lists every host the collector may contact for that kommun; `region_code` must be the
   first two digits of the kommun code.
6. Add a trimmed listing fixture as `collector/tests/fixtures/municipal/<code>-listing.html` (headings
   and links are all the parser reads) and its expectations as `collector/tests/fixtures/municipal/<code>.json`
   (`listings`: every page read, followed pages included, to its fixture file, `count`, a `sample` entry with `number`, `title` and `url`,
   and `excluded` titles); `test_municipal_listings.py` checks every such pair against the config. Then
   run a small sample with `--kommun <code> --limit 5` and the audit.

## Agencies and sources log

```sh
python3 -I collector/agencies.py             # rebuild from the cached index and court list
python3 -I collector/agencies.py --refresh   # fetch lagrummet.se's index and the court list again first
```

Writes `AGENCIES.md`, `collector/data/agencies-report.json` and the landing page catalog
`landing/data/sources.json`: every agency regulation series (författningssamling), agency
publishing in another agency's series, county, kommun, court and other legal source, with a link to
its official page, its status (collected, metadata and PDF links only, partly collected, blocked,
API key needed, robots.txt, no adapter yet, no report number, out of scope), the reason for each gap
and the issue that tracks it.

- The list of series and sources is lagrummet.se's rättskällor index
  (`https://www.lagrummet.se/rattskalla/`), which lists every entry on one page with the link to the
  official page and a Swedish description. It is cached in `collector/data/rattskalla.json`, keyed by
  a slug of the entry's title. The per-entry pages in lagrummet.se's sitemap answer 404 and are not
  used.
- The courts are the rättspraxis API's court list (`/api/v1/domstolar`), cached in
  `collector/data/courts.json`; each court links to its guiding decisions on rättspraxis.
- `--refresh` reads each host's robots.txt, then the index and the court list: four requests,
  `--rate` apart (default 2 s).
- Agency names, statuses and notes are curated in `collector/data/agencies.json`, keyed by slug:
  `series` (own series), `shared` (an agency that publishes in another series; it takes that series'
  status) and `sources` (SFS, case law, EU and other sources); `courts` holds notes and statuses per
  court code and `issues` the tracking issue per entry (`series:AFFS`, `county:01`, `kommun:0114`,
  `court:KGG`, `source:<slug>`). County series are recognised from their slug. A series without a
  status is `collected` when the corpus has documents with its prefix, otherwise `no adapter yet`; an
  index entry missing from the file is listed as unclassified.
- Kommun websites are in `collector/data/kommuner.json` (official website of each kommun in
  Wikidata, normalised to the https root and checked by hand). The Wikidata query service disallows
  `/sparql` in its robots.txt, so the file is maintained by hand rather than fetched.
- Counts come from the corpus (series prefix of `number`, kommun code of `id`, `court`), the
  county and kommun configuration from `counties.json` and `municipalities.json`, the list of
  counties and kommuner from the app's `files/geo/sweden.json`, kommun gaps from
  `sources/municipal-manifest.json`.

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing, list file or robots.txt could not be read, or the state file is corrupt
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

These apply to `sfs`, `case-law` and `agency`.
These apply to `sfs`, `case-law` and `county`.

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
