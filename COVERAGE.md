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
| EU law | Publications Office Cellar: SPARQL `https://publications.europa.eu/webapi/rdf/sparql` and `https://publications.europa.eu/resource/celex/<CELEX>` (Swedish) | 2026-10-29 (curated list) |

The SFS target (11567 documents) is the number Riksdagen lists for document
type `sfs` on that date, all statute types together.

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
- Phases 2 and 3 are otherwise not started: agency regulations, case law, regional
  and municipal regulations and public services have no collector yet and no known
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
