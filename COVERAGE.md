# Coverage

What the corpus covers, what it does not, and where the numbers come from.
Counts per series are in [PROGRESS.md](PROGRESS.md). Volume does not prove
completeness: read this file next to those numbers.

## Sources and cut-off

| layer | source | cut-off |
| --- | --- | --- |
| fundamental, SFS | Riksdagen open data, `https://data.riksdagen.se/dokumentlista/?doktyp=sfs` and `https://data.riksdagen.se/dokument/<id>` | 2026-10-27 |

The SFS target (11567 documents) is the number Riksdagen lists for document
type `sfs` on that date, all statute types together.

## Known gaps

- `in_force` is `null` everywhere: the source does not provide an entry-into-force
  date and dates in prose are not parsed.
- Some older acts are available only in print. They are kept as stubs with a
  "Text available only in print" note and are flagged `print_only` by the audit.
- N-series (Norrland-style `N` prefixed) numbering is stored as published, with
  the `N` prefix kept in ids and numbers; the audit compares numbers literally.
- Amendment history is not reconstructed. `amended_by`, `amended_through` and
  `reprinted_by` only list numbers; many of them point to acts not yet collected
  (the audit reports the count). History reconstruction is tracked in #7.
- Authoritative PDFs are not snapshotted, so documents are marked
  `authoritative: false`. Tracked in #8.
- Phases 2 and 3 are not started: agency regulations, case law, EU law, regional
  and municipal regulations and public services have no collector yet and no known
  target.

## Failures and blocked sources

The SFS collector records documents it cannot fetch or parse in its state file
(`collector/data/sfs-state.json`, not committed) with state `failed`, and retries
them on the next run. Sources that block automation, require a captcha or sit
behind a paywall are never bypassed; they are listed here as gaps instead.
Currently no source is blocked.

## Integrity

`python3 -I collector/audit.py` checks every file against the schema, duplicate
ids, file paths, text quality and cross-references and writes
`collector/data/pending-integrity.json`.
