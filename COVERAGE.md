# Coverage

What the corpus covers, what it does not, and where the numbers come from.
Counts per series are in [PROGRESS.md](PROGRESS.md). Volume does not prove
completeness: read this file next to those numbers.

## Sources and cut-off

| layer | source | cut-off |
| --- | --- | --- |
| fundamental, SFS | Riksdagen open data, `https://data.riksdagen.se/dokumentlista/?doktyp=sfs` and `https://data.riksdagen.se/dokument/<id>` | 2026-10-27 |
| SFS PDF manifest | `https://svenskforfattningssamling.se/regulations/<year>/index.html` and `/doc/<year><number>.html` | 2026-10-28 (sample) |
| SFS amendment register | `https://rkrattsbaser.gov.se/sfsr?bet=<number>` | 2026-10-28 (pilot: 1974:152, 1962:700, 1998:808) |
| agency regulations | Arbetsmiljöverket `https://www.av.se/.../publikationer/foreskrifter/`, Finansinspektionen `https://www.fi.se/sv/vara-register/fffs/forteckning-fffs/`, Transportstyrelsen `https://www.transportstyrelsen.se/.../ts-foreskrifter-i-nummerordning/<year>/` | 2026-10-29 (sample: AFS 2023:1–5, FFFS 2024:21, 2024:22, 2025:2, 2025:8, 2025:13, TSFS 2026:6, 11, 13, 19, 20) |
| EU law | Publications Office Cellar: SPARQL `https://publications.europa.eu/webapi/rdf/sparql` and `https://publications.europa.eu/resource/celex/<CELEX>` (Swedish) | 2026-10-29 (curated list) |
| regional (county) | Länsstyrelserna, `https://www.lansstyrelsen.se/<county>/om-oss/om-lansstyrelsen-<county>/lanets-forfattningssamling/forfattningar-<year>.html` and the linked detail pages | 2026-10-29 (pilot: 01FS 2026:1–10, Stockholm) |
| case law | Sveriges Domstolar, `https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar` (referat and notiser) | 2026-10-29 (sample: NJA 2026:29–38, HFD 2026 ref. 35–43, HFD 2026 not. 24) |
| municipal regulations | Stockholm `https://start.stockholm/om-stockholms-stad/politik-och-demokrati/styrdokument/kommunal-forfattningssamling/`, Göteborg Domino view `https://www4.goteborg.se/prod/Stadsledningskontoret/LIS/Verksamhetshandbok/Forfattn.nsf/vyHandBok`, Malmö `https://malmo.se/Om-Malmo-stad/Demokrati-och-politik/Sa-styrs-Malmo/Forfattningssamling/` (citizen rules and taxor pages) | 2026-10-29 (sample: five documents per kommun) |

The SFS target (11567 documents) is the number Riksdagen lists for document
type `sfs` on that date, all statute types together.

The case-law target (16640 documents) is the number of referat and notiser the
Sveriges Domstolar API lists (`x-total-count`) on 2026-10-29, all courts together.

## Known gaps

- `in_force` and `amendments` come from the SFS register (SFSR) and are filled
  only for the pilot statutes (Regeringsformen, Brottsbalken, Miljöbalken). All
  other statutes have `in_force: null` and no `amendments`: Riksdagen gives no
  entry-into-force date and dates in prose are not parsed. The register itself
  has no `Ikraft` for Regeringsformen and for most amendments before about 1982.
- Some older acts are available only in print. They are kept as stubs with a
  "Text available only in print" note and are flagged `print_only` by the audit.
- N-series numbering (numbers with an `N` prefix) is stored as published, with
  the `N` prefix kept in ids and numbers; the audit compares numbers literally.
- Amendment history is metadata only. `collector/history.py` builds one commit
  per amendment from the register (pilot statutes), dated at entry into force or
  a noted fallback, but historical text is not reconstructed: no open source has
  consolidated text as of a past date. `amended_by`, `amended_through` and
  `reprinted_by` only list numbers; many of them point to acts not yet collected
  (the audit reports the count).
- Authoritative PDFs from svenskforfattningssamling.se (acts published from
  2018-04 on) are recorded in `sources/sfs-pdf-manifest.json` with their
  SHA-256, but only a five-act sample of 2026 is in it so far; the full crawl
  has not run. The PDF bytes are not stored, and the documents stay marked
  `authoritative: false` until the corpus text is tied to a snapshot.
- EU law covers only the curated list in `collector/data/eu-acts.json` (43
  acts: 40 Official Journal texts and 3 consolidated versions); its target is that
  list, not the roughly 47,000 acts in force. Three acts have Swedish only as PDF or
  print in the Cellar: REACH (32006R1907), Regulation (EC) No 883/2004
  (32004R0883) and Directive 2004/38/EC (32004L0038). They are recorded as gaps in
  `sources/eu-manifest.json`, and their latest consolidated versions, which have no
  legal effect (`authoritative: false`), are in the corpus instead. Consolidated
  versions of the other acts are not collected yet. Tables are flattened to one line
  per row, and `amended_through` is not filled.
- Case law: only a 20-document sample of the latest Högsta domstolen and Högsta
  förvaltningsdomstolen publications is in the corpus; the full run has not
  started. Only the anonymised referat and notiser are collected. Rulings the
  courts publish in full (`DOM_ELLER_BESLUT`, about 760), leave-to-appeal and
  preliminary-ruling notices and all attachments (PDF) are left out by design.
  Publications without a report reference in the schema's form, and any whose
  text contains a personal identity number, are recorded as failed instead of
  written. SFS references (`lagrumLista`) are kept in the body only; they are
  not yet links to the SFS layer.
- Agency regulations: only a 15-document pilot sample of three series (AFS,
  FFFS, TSFS) is in the corpus; about 100 series exist (lagrummet.se lists them)
  and there is no known target. Only base regulations are stored; amending
  regulations are listed in `amended_by`. AFS has the consolidated text from
  Arbetsmiljöverket's HTML pages. FFFS and TSFS publish the text only as PDF:
  their bodies hold metadata, the agency's summary and links to the PDFs, whose
  SHA-256 is in `sources/agency-pdf-manifest.json`; PDF text is not extracted.
  `issued` is known only for unamended AFS regulations, and AFS `in_force` only
  for those; FFFS and TSFS have no decision date on their pages.
  Arbetsmiljöverket's robots.txt disallows its folder of original PDFs, which is
  never requested. Boverket (BFS, API key probably needed, owner to decide),
  Skatteverket (SKVFS, robots.txt request rejected by a WAF) and the other
  series are not collected yet.
- Regional and municipal regulations and public services have no collector
  yet and no known target.
- Regional regulations: only a pilot of ten Stockholm regulations (01FS
  2026:1–10) is in the corpus. Stockholm's site lists 2020–2026 (38
  regulations in 2026 by 2026-10-29); older years and the other 20 counties are
  not collected yet, and only Stockholm's landing page has been checked. The
  text comes from the HTML version on each detail page; the printed PDF is
  recorded by URL and SHA-256 but not parsed, so a regulation published only as
  PDF has no text. `repealed` and amendment links are not filled (the site
  publishes no status), and `in_force` only when the text names one date. Local
  traffic regulations (Transportstyrelsen's STFS) and the self-governing regions
  are out of scope. No target is set: the total volume is not measured yet.
- Agency regulations, municipal regulations and public services have no
  collector yet and no known target.
- Municipal regulations: only a pilot sample of 15 documents (five each from
  Stockholm, Göteborg and Malmö) is in the corpus; the other 287 kommuner have no
  config entry yet and there is no known target (roughly 30–150 documents per
  kommun). Scope decision: only rules that bind residents are collected (lokala
  ordningsföreskrifter, föreskrifter om avfall, renhållning and naturreservat,
  hamnordningar, taxor and avgifter); internal governance documents
  (reglementen, arbetsordningar, instruktioner, bolagsordningar, ägardirektiv,
  delegationsordningar, stadgar) are left out. The text is published as PDF and
  is not extracted: bodies hold metadata, the kommun's note and links to the
  PDFs, whose SHA-256 is in `sources/municipal-manifest.json`. `issued` and
  `in_force` are not filled. Kommun-specific gaps:
  - Malmö: robots.txt disallows `/download/*`, where every PDF lives, so the
    PDFs are never fetched; the documents point at the listing page and are
    recorded as gaps in the manifest. Malmö prints no local number, so `number`
    is the Sitevision id of the file. Links to other pages (hundstadga,
    lokala trafikföreskrifter, VA SYD's rules) are not collected.
  - Stockholm: the general lokala ordningsföreskrifter are an HTML page, not a
    KFS PDF, and are not collected yet.
  - Göteborg: the source is the city's "styrande dokument" handbook
    (`Forfattn.nsf`), filtered to the kinds "Lokal föreskrift" and
    "Taxor/avgifter"; `number` is the handbook serial number (`N010G…`), as
    Göteborg prints no KFS-style number. The detail pages carry a
    `noindex,nofollow` robots meta tag (a search-engine indexing hint);
    robots.txt allows the paths.
- Regional regulations and public services have no collector yet and no known
  target.

## Failures and blocked sources

The SFS collector records documents it cannot fetch or parse in its state file
(`collector/data/sfs-state.json`, not committed) with state `failed`, and retries
them on the next run. Sources that block automation, require a captcha or sit
behind a paywall are never bypassed; they are listed here as gaps instead.
EUR-Lex (`eur-lex.europa.eu`) answers automated clients with an AWS WAF
challenge, so it is never used; EU texts come from the Cellar instead. Currently no source is blocked.

## Integrity

`python3 -I collector/audit.py` checks every file against the schema, duplicate
ids, file paths, text quality and cross-references and writes
`collector/data/pending-integrity.json`.
