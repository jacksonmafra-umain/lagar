# Static JSON API (v1)

The app reads only this API, never the corpus. All files are static JSON served
under `/api/v1/`. All paths below are relative to that prefix.

Conventions:

- JSON is UTF-8. All keys are `snake_case`.
- Dates are `YYYY-MM-DD`. Timestamps are UTC, `YYYY-MM-DDTHH:MM:SSZ`.
- `null` is used for unknown or not-applicable values; keys are never omitted.
- Canonical examples live in `docs/api/examples/` and mirror the paths below.
  They include a series listing (`sfs/ordinance/index-1.json`), an empty layer
  listing (`eu/index-1.json`: `items: []`, `page_count: 1`, `total: 0`) and
  per-locality listings (`region/by-code/`, `municipality/by-code/`).

## Vocabulary

Layers (fixed order): `fundamental`, `sfs`, `agency`, `case_law`, `eu`,
`region`, `municipality`, `service`.

Types, the layer each belongs to, and the corpus folder the collector writes
them to (the folder is not part of the API; it is listed here so the corpus
layout has one reference). Within a layer, `series` lists types in this order.

| type | layer | what it is | corpus folder |
| --- | --- | --- | --- |
| `fundamental_law` | `fundamental` | grundlag | `fundamental-laws/` |
| `act` | `sfs` | SFS lag | `sfs/acts/` |
| `ordinance` | `sfs` | SFS förordning | `sfs/ordinances/` |
| `other_statute` | `sfs` | other SFS statute | `sfs/other/` |
| `agency_regulation` | `agency` | myndighetsföreskrift (with or without allmänna råd) | `agency/regulations/` |
| `case_report` | `case_law` | referat | `case-law/reports/` |
| `case_notice` | `case_law` | notis | `case-law/notices/` |
| `eu_regulation` | `eu` | EU regulation | `eu/regulations/` |
| `eu_directive` | `eu` | EU directive | `eu/directives/` |
| `eu_decision` | `eu` | EU decision | `eu/decisions/` |
| `county_regulation` | `region` | länsstyrelsens föreskrift (länets författningssamling) | `region/county-regulations/` |
| `municipal_regulation` | `municipality` | kommunal föreskrift (kommunens författningssamling) | `municipality/regulations/` |

File names are the document id plus `.md`, without the `sfs-` prefix for SFS
and fundamental laws and without the `eu-` prefix for EU acts
(`sfs/acts/2010-800.md`, `eu/regulations/32016r0679.md`,
`agency/regulations/afs-2023-1.md`).

### Number formats

`number` and the reference fields (`amended_by`, `amended_through`,
`reprinted_by`) are checked per type:

| types | `number` | references |
| --- | --- | --- |
| SFS and fundamental laws | free text; normally `1999:175` or `N2026:1`, old prints keep Riksdagen's numbering | `^N?\d{4}:\d+$` |
| `agency_regulation` | series, year and ordinal: `AFS 2023:1`, `FFFS 2014:1`, `HSLF-FS 2016:40` | same form as `number` |
| `county_regulation` | county series: `01FS 2024:3` (`<region_code>FS`) | same form as `number` |
| `case_report`, `case_notice` | report reference: `NJA 2019 s. 2`, `HFD 2020 ref. 5`, `HFD 2020 not. 3`, `NJA 2004 N 23`, `MIG 2026:10`, `AD 2020 nr 45`; a kammarrätt referat published without one (KGG, KJO, KST, KSU) is cited by the court's abbreviation, decision date and case number: `KRNJ 2007-01-09 mål nr 1097-06` (series `KRNG`, `KRNJ`, `KRNS`, `KRSU`) | none: `amended_by` and `reprinted_by` are `[]`, `amended_through` is `null` |
| `eu_regulation`, `eu_directive`, `eu_decision` | Swedish citation form: `(EU) 2016/679`, `(EG) nr 1907/2006`, `95/46/EG` | CELEX numbers (`32016R0679`); `reprinted_by` is `[]` |
| `municipal_regulation` | the local number as printed, any non-empty text without surrounding spaces | any non-empty text |

## Display levels

The app shows nine levels; API layers map onto them as follows.

| display level | API source |
| --- | --- |
| fundamental | layer `fundamental` |
| SFS acts | layer `sfs`, type `act` (SFS lagar) |
| SFS ordinances | layer `sfs`, type `ordinance` (SFS förordningar) |
| agency | layer `agency` |
| case law | layer `case_law` |
| EU | layer `eu` |
| region | layer `region` |
| municipality | layer `municipality` |
| service | layer `service` |

Type `other_statute` (layer `sfs`) is shown under the SFS acts colour group as
"other statutes". The types of the other layers take their layer's level and
colour: `case_report` and `case_notice` are case law, the three `eu_*` types
are EU, `agency_regulation` is agency, `county_regulation` is region and
`municipal_regulation` is municipality.

`DESIGN.md` palette keys use hyphens (`case-law`, `sfs-act`, `sfs-ordinance`);
API ids use underscores (`case_law`, `act`, `ordinance`).

## `GET index.json`

| field | type | null | notes |
| --- | --- | --- | --- |
| `api_version` | integer | no | currently `1` |
| `built_at` | string (UTC timestamp) | no | |
| `layers` | array of layer | no | all eight layers, in the order above |

Layer object:

| field | type | null | notes |
| --- | --- | --- | --- |
| `id` | string | no | layer id |
| `count` | integer | no | documents in the layer |
| `series` | array of series | no | only types with `count` > 0; `[]` when the layer is empty |

Series object: `id` (string, a type, not null) and `count` (integer, not null).

Series rule: `series` lists only types with `count` > 0, so an empty layer has
`series: []`.

Empty-layer rule: a layer with no documents is still listed, with `count: 0`
and `series: []`. `<layer>/index-<page>.json` exists for every layer; an empty
layer has `index-1.json` with `items: []` and `page_count: 1`.
`<layer>/<type>/index-<page>.json` exists only for types listed in `series`.

## `GET <layer>/index-<page>.json` and `GET <layer>/<type>/index-<page>.json`

Paged listings: per layer, and per type within a layer. Pages are 1-based
(`index-1.json` is the first), 50 items per page.

| field | type | null | notes |
| --- | --- | --- | --- |
| `layer` | string | no | layer id |
| `type` | string | yes | type id for `<layer>/<type>/` listings, `null` for the layer listing |
| `page` | integer | no | this page, from 1 |
| `page_count` | integer | no | at least 1, even when empty |
| `total` | integer | no | items across all pages |
| `items` | array of item | no | up to 50; `[]` for an empty layer |

Item object:

| field | type | null | notes |
| --- | --- | --- | --- |
| `id` | string | no | document id, always lowercase, e.g. `sfs-1999-175` or `sfs-n2026-1` |
| `title` | string | no | |
| `number` | string | no | e.g. `1999:175`; N-series ordinances (published outside the printed SFS) start with `N`, e.g. `N2026:1`; other layers use their own forms, see Number formats |
| `type` | string | no | type id |
| `issued` | string (date) | yes | |
| `repealed` | string (date) | yes | |
| `in_force` | string (date) | yes | entry into force; same value as `meta.in_force` |
| `amended_through` | string | yes | number of the latest amendment (an SFS number for SFS types, see Number formats); same value as `meta.amended_through` |
| `ministry` | string | yes | issuing ministry or body; same value as `meta.ministry` |
| `region_code` | string | yes | county code (`01`–`25`); same value as `meta.region_code`. Set for `county_regulation` and usually for `municipal_regulation`, `null` elsewhere |
| `municipality_code` | string | yes | four-digit kommun code; same value as `meta.municipality_code`. Set for `municipal_regulation`, `null` elsewhere |

Keys appear in the order above. `in_force`, `amended_through`, `ministry`,
`region_code` and `municipality_code` were added within v1: they are always
present but may be `null`, and they come after the original keys (the two
locality codes last). The change is additive, so v1 clients that ignore
unknown keys keep working; clients should treat the five fields as optional
and nullable.

Sort order: `issued` descending, then `number` descending, across pages. `number` is compared numerically by (year, ordinal), not as a string, so `1999:175` comes before `1999:99`. A series prefix (`N`, `RFS`) is ignored for ordering; on a tie the plain number is listed before the prefixed one (`2026:5` before `N2026:5`). Old prints keep Riksdagen's numbering, such as `1827:60 s.1007` or `1899:bih. 25`: non-digits before the ordinal are skipped and the rest after it only breaks ties. Items
with `issued: null` sort after dated ones.

The other layers' numbers are also compared by (year, ordinal), descending:

- `agency_regulation`, `county_regulation`: year and ordinal after the series
  (`AFS 2023:10` before `AFS 2023:9`); on a tie the series name descending.
- `case_report`, `case_notice`: year and the number after it, which is the
  page for `NJA … s.` and the report or notice number otherwise (the case
  number's ordinal for `KRNJ 2007-01-09 mål nr 1097-06`); on a tie the report
  series descending.
- EU types: the act's year and number. `(EU) 2016/679` is year/number; with
  `nr`, `(EG) nr 1907/2006` and `(EEG) nr 1408/71` are number/year; directives
  and decisions such as `95/46/EG` and `2004/18/EG` are year/number. A
  two-digit year is 19xx.
- `municipal_regulation`: the first year (1600–2099) in the number and the
  digits that follow it (`SKFS 2024:12` is (2024, 12)); a number without a
  year sorts as (0, 0), after the others; ties by the full number.

## By ministry: `GET <layer>/<type>/by-ministry/index.json` and `GET <layer>/<type>/by-ministry/<ministry>/index-<page>.json`

Added within v1 (additive: no existing file changes). For each type of the
`sfs` layer listed in `series`, the documents grouped by issuing ministry, so
a client can browse by ministry without reading every listing page. Other
layers have no per-issuer index yet. Examples:
`docs/api/examples/sfs/ordinance/by-ministry/`.

Grouping: the item's `ministry` with surrounding and repeated whitespace
removed and, when it names a ministry (`…departementet`), without the unit
code that follows (`Justitiedepartementet L2` and `Justitiedepartementet DOM`
are both `Justitiedepartementet`). Other bodies (`Riksbanken`,
`Statistiska centralbyrån`) are kept as written. Items with `ministry: null`
are left out and counted in `unassigned`.

Ministry id: the name lowercased, `å`/`ä`/`æ` → `a`, `ö`/`ø` → `o`, `é`/`è` → `e`, `ü` → `u`, and
every run of other characters than `a-z0-9` as one `-`, trimmed
(`Klimat- och näringslivsdepartementet` → `klimat-och-naringslivsdepartementet`).
Two names with the same id fail the build.

### `<layer>/<type>/by-ministry/index.json`

| field | type | null | notes |
| --- | --- | --- | --- |
| `layer` | string | no | layer id |
| `type` | string | no | type id |
| `total` | integer | no | documents of the type, with or without a ministry |
| `unassigned` | integer | no | documents with `ministry: null` |
| `ministries` | array of ministry | no | `count` descending, then `name`; `[]` when no document has a ministry |

Ministry object: `id` (string, the ministry id), `name` (string, the grouped
name) and `count` (integer, documents in the group). None are null.

### `<layer>/<type>/by-ministry/<ministry>/index-<page>.json`

A paged listing like `<layer>/<type>/index-<page>.json` (same item object,
sort order and page size), with two keys after `type`: `ministry_id` (the
ministry id) and `ministry` (the grouped name). Items keep their own
`ministry` value as written, unit code included. A listing exists only for the
ids in the index.

## By code: `GET <layer>/by-code/index.json` and `GET <layer>/by-code/<code>/index-<page>.json`

Added within v1 (additive: no existing file changes). The `region` layer is
grouped by `region_code` (one län each) and the `municipality` layer by
`municipality_code` (one kommun each), so a client shows the documents of the
user's län or kommun without reading the whole layer. Examples:
`docs/api/examples/region/by-code/` and `docs/api/examples/municipality/by-code/`.

Why per-code listings rather than only the item fields: a kommun home needs a
few dozen documents out of what will be thousands across 290 kommuner, and
filtering the layer listing client-side would mean reading every page of it.
The codes are also on every listing item and in the search `docs.json`, for
search and for clients that already hold the whole layer.

### `<layer>/by-code/index.json`

Exists for `region` and `municipality`, also when the layer is empty.

| field | type | null | notes |
| --- | --- | --- | --- |
| `layer` | string | no | `region` or `municipality` |
| `field` | string | no | the item key the layer is grouped by: `region_code` or `municipality_code` |
| `total` | integer | no | documents in the layer |
| `codes` | array of code | no | codes with at least one document, ascending; `[]` when the layer is empty |

Code object: `code` (string, a county or kommun code) and `count` (integer,
documents with that code). Neither is null. The schema requires the code on
every document of these layers, so the counts add up to `total`.

### `<layer>/by-code/<code>/index-<page>.json`

A paged listing like `<layer>/index-<page>.json` (same item object, sort order
and page size; `type` is `null`), with one key after `type`: `code`. A listing
exists only for the codes in the index; a code that is not listed has no
documents, so clients show their empty state without requesting it.

## `GET docs/<id>.json`

| field | type | null | notes |
| --- | --- | --- | --- |
| `meta` | object | no | all frontmatter fields, below |
| `body` | string | no | Markdown: `# <title>`, paragraphs, section numbers as `**1 §**` |

### `meta` fields

`amended_through` is the last amending SFS number according to the source. It
can be set while `amended_by` is empty or partial: `amended_by` lists only the
amending SFS numbers found in the text.
For EU types, `amended_through` is the CELEX number of the latest amending act
a consolidated version applies, and `null` for the Official Journal text.

`in_force` and `amendments` come from the SFS register (SFSR) at
<https://rkrattsbaser.gov.se/sfsr>, which only some statutes have been read
from so far. Until then `in_force` is `null` and `amendments` is `null`. Once
read, `amendments` is the register's full list of amending acts, so it is
usually longer than `amended_by`.

Keys are always present, in this order. They mirror the corpus frontmatter
(`docs/schema/frontmatter.schema.json`); `amendments` and the six fields after
it are optional in the frontmatter, and the API then serves them as `null`.

| field | type | null | notes |
| --- | --- | --- | --- |
| `id` | string | no | `^[a-z0-9_]+-[0-9a-z-]+$` |
| `title` | string | no | |
| `type` | string | no | one of the types above |
| `layer` | string | no | one of the layers; must equal the layer of `type` |
| `number` | string | no | |
| `issued` | string (date) | yes | |
| `in_force` | string (date) | yes | entry into force of the statute itself, from SFSR |
| `repealed` | string (date) | yes | |
| `amended_by` | array of string | no | for SFS types each `^N?\d{4}:\d+$` (N-series numbers keep their `N`); other types see Number formats; may be empty |
| `amended_through` | string | yes | number of the latest amendment applied; for SFS types `^N?\d{4}:\d+$` |
| `reprinted_by` | array of string | no | for SFS types each `^N?\d{4}:\d+$`; may be empty |
| `ministry` | string | yes | |
| `eli` | string (URI) | yes | |
| `language` | string | no | `sv` or `en` |
| `authoritative` | boolean | no | |
| `source` | string (URI) | no | |
| `source_sha256` | string | no | 64 lowercase hex characters |
| `fetched_at` | string (UTC timestamp) | no | |
| `amendments` | array of amendment | yes | `null` until read from SFSR; `[]` when the register lists none. Added in v1 without a version bump |
| `issuer` | string | yes | issuing body of a non-SFS document: agency, county board, kommun, court or EU institution. Always `null` for SFS types (they use `ministry`) |
| `court` | string | yes | court code as used by Sveriges Domstolar, `^[A-ZÅÄÖ0-9]{2,10}$`, e.g. `HDO`, `HFD`. Required for case law, `null` elsewhere |
| `ecli` | string | yes | European Case Law Identifier, e.g. `ECLI:SE:HDO:2019:2`. Case law only |
| `celex` | string | yes | CELEX number, e.g. `32016R0679` or `02016R0679-20160504` for a consolidated version. Required for EU types, `null` elsewhere |
| `region_code` | string | yes | county code, `01`–`25` as used by SCB (`01` Stockholm … `25` Norrbotten). Required for `county_regulation` and equal to its series prefix; allowed for `municipal_regulation`; `null` elsewhere |
| `municipality_code` | string | yes | four-digit SCB kommun code, e.g. `0180` Stockholm; starts with `region_code` when both are set. Required for `municipal_regulation`, `null` elsewhere |

The last six fields were added within v1, after `amendments`, without a
version bump: every document carries them, as `null` where they do not apply.

### Amendment object

One per "Ändring" entry of the register, in register order (by SFS number).
All keys are always present.

| field | type | null | notes |
| --- | --- | --- | --- |
| `number` | string | no | amending SFS number, `^N?\d{4}:\d+$` |
| `title` | string | yes | e.g. `Lag (1983:240) om ändring i brottsbalken`; older entries often have none |
| `scope` | string | yes | the register's `Omfattning`, e.g. `ändr. 26 kap. 6 §` (`ändr.` amended, `upph.` repealed, `nya` new) |
| `preparatory_works` | string | yes | the register's `Förarbeten` (bill, committee report, Riksdag communication) |
| `celex` | string | yes | CELEX numbers of EU acts the amendment implements, as listed |
| `in_force` | string (date) | yes | entry into force when the register value starts with a date; `null` when it is missing (common before about 1982) or not a date |
| `in_force_raw` | string | yes | the register value as written, whitespace collapsed, e.g. `1983-07-01 överg.best.` (transitional provisions apply) or a condition such as `den dag regeringen bestämmer`; `null` when missing |

## Full-text search: `GET search/index.json`, `search/<group>/index.json`, `search/<group>/docs.json`, `search/<group>/shards/<key>.json`

A static inverted index, split by layer. The client reads the top-level
manifest, picks the groups of the layers it searches, tokenises the query
with the rules below and fetches only the shards its terms fall in, per
group. Examples: `docs/api/examples/search/` (built from the API test fixture
corpus; only two shards per group are copied).

The index has its own format version, `search_version`, independent of
`api_version`: the search files are an optional extra that clients detect
through the manifest. Version 2 (current) replaced version 1, a single index
over every layer; see Versions below.

### Text normalisation and tokens

Index and query text go through the same steps, which match the app's
`normalize()` in `app/shared/.../domain/Search.kt` (so `Åre` matches `are`):

1. Lowercase.
2. Fold diacritics character by character: each character of
   `normalization.fold_from` becomes the character at the same position in
   `normalization.fold_to` (`å`/`ä` → `a`, `ö` → `o`, `é` → `e`, ...). Other
   characters, such as `ü` or `æ`, are kept.
3. Split into tokens with `normalization.token_pattern`
   (`[a-z]*\d{4}:\d+|[^\W_]+`, Unicode-aware, applied to the folded text): an
   SFS number such as `1962:700` or `n2026:1` is one token; otherwise a token is
   a run of letters and digits. Everything else separates tokens.
4. Drop single-letter tokens (single digits such as the `5` in `5 §` stay) and
   the short list of Swedish function words in `normalization.stop_words`
   (`och`, `att`, `om`, `for`, ...). Words such as `lag`, `kap` or `inte` stay.

### `search/index.json` (top-level manifest)

| field | type | null | notes |
| --- | --- | --- | --- |
| `search_version` | integer | no | `2`; bumped on an incompatible format change |
| `built_at` | string (UTC timestamp) | no | same as `index.json`; cache group manifests, document tables and shards keyed by it, since document numbers change between builds |
| `doc_count` | integer | no | documents over all groups |
| `term_count` | integer | no | sum of the groups' `term_count` (a term in two groups counts twice) |
| `field_bits` | object | no | bit per field: `title` 1, `number` 2, `body` 4 |
| `posting_bits_base` | integer | no | `8`: a posting is `gap * 8 + bits` (below) |
| `normalization` | object | no | `lowercase`, `fold_from`, `fold_to`, `token_pattern`, `min_length` (2), `keep_single_digits` (true), `stop_words` (sorted) |
| `shard_key_length` | integer | no | `2` |
| `groups` | array of group | no | one per layer with documents, in layer order; a layer without documents has no group |

Group object:

| field | type | null | notes |
| --- | --- | --- | --- |
| `id` | string | no | group id; today always the layer id, and the group's files are under `search/<id>/` |
| `layers` | array of string | no | layers whose documents the group holds; today one, `[<id>]`. Clients pick groups by this list, not by `id` |
| `doc_count` | integer | no | rows in the group's `docs.json` |
| `fields` | array of string | no | indexed fields: `title`, `number`, and `body` when the group fits its budget (Size budget below) |
| `bytes` | integer | no | size of the group's files (manifest, `docs.json` and shards), uncompressed |
| `budget` | integer | no | the group's budget in bytes |

### `search/<group>/index.json` (group manifest)

| field | type | null | notes |
| --- | --- | --- | --- |
| `group` | string | no | group id |
| `layers` | array of string | no | as in the group object |
| `doc_count` | integer | no | rows in `docs.json` |
| `term_count` | integer | no | distinct terms over the group's shards |
| `fields` | array of string | no | as in the group object |
| `shards` | array of shard | no | sorted by `key`; only keys that have terms |

Shard object: `key` (string), `terms` (integer, terms in the shard) and
`bytes` (integer, size of the shard file).

### `search/<group>/docs.json`

`fields` lists the column names, a subset of `id`, `title`, `number`, `type`,
`issued`, `repealed`, `region_code`, `municipality_code` in that order (same
values as listing items); `docs` is one row per document of the group, sorted
by `id`. A document's number in the group's postings is its 0-based row
index. A column that is `null` in every row of the group is left out (the
case-law group has no locality columns, for example); `id` is always there.
Clients read columns by name and treat a missing column as `null`. The
locality codes let a client narrow a search to the user's län or kommun.

### `search/<group>/shards/<key>.json`

`key` is the first two characters of a term, with any character outside
`a-z` and `0-9` replaced by `_` (`skollag` → `sk`, `1962:700` → `19`,
`über` → `_b`). A one-character term (a single digit) has a one-character key,
for example `5`. A shard exists only when the group manifest lists its key.

| field | type | null | notes |
| --- | --- | --- | --- |
| `key` | string | no | shard key |
| `terms` | object | no | term → postings, terms sorted |

Postings are a flat integer array, one integer per document, by ascending
document number: `gap * 8 + bits` (`posting_bits_base` is 8). `gap` is the
document number itself for the first posting and the difference to the
previous document after that; `bits` (the remainder) is the OR of the
`field_bits` the term occurs in for that document (5 = title and body).
Example: `"utbildning": [12]` means document 1 (12 / 8) has `utbildning` in
its body (12 % 8 = 4); `[1, 9, 9]` is documents 0, 1 and 2, each in the title.

### Querying

- Groups: read the groups whose `layers` overlap the layers being searched
  (the app's Nationell scope reads `fundamental`, `sfs`, `agency`,
  `case_law` and `eu`; Region and Kommun read one group each). Document
  numbers are per group, so run the query in each group and merge the hits
  by document id.
- Exact term: look the term up in its shard.
- Prefix (type-ahead): every term starting with the typed text is in the same
  shard as long as the text has at least two characters, so filter the shard's
  sorted terms by prefix.
- Several terms: intersect the document sets within a group. A suggested
  rank across groups: documents matching in the title first, then number,
  then body only (lowest bit set). Filters (type, dates, status, locality)
  apply to `docs.json` rows.

### Versions

| version | layout | postings |
| --- | --- | --- |
| 1 | one index over every layer: `search/index.json` holds `fields` and `shards`, `search/docs.json`, `search/shards/<key>.json` | `[gap, bits, gap, bits, ...]` |
| 2 | one group per layer, as above | `[gap * 8 + bits, ...]` |

Rollout: the API publishes only the current version; old files are not kept,
because keeping both would double the index (about 80 MB). The app reads both
versions (version 1 as one group over every layer), so an app built after
version 2 works against either API. An app build that reads only version 1
sees an unknown `search_version`, ignores the index and falls back to listing
search (titles and numbers from the listings), as it does when the API has no
index. The web app is deployed with the API in one Pages build, so it always
matches.

### Size budget

Each group gets body text only when the whole group (manifest, `docs.json`
and shards, uncompressed) fits its budget; otherwise that group falls back to
titles and numbers and its `fields` say so, while other groups keep their
bodies. Budgets live in `api/searchindex.py`: `case_law` 80 MB, every other
layer 40 MB. The frontmatter has no summary field yet, so titles and numbers
are the only metadata indexed.

Measured on the full corpus (27 901 documents, built 2026-10-29):

| group | documents | files | uncompressed | gzip (sum per file) | terms | `docs.json` | largest shard |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fundamental` | 4 | 207 | 72 KB | 29 KB | 3 256 | 0.4 KB | 4.6 KB (`fo`) |
| `sfs` | 11 424 | 1 039 | 18.4 MB | 5.6 MB | 216 517 | 1.7 MB | 0.9 MB (`fo`) |
| `agency` | 15 | 329 | 144 KB | 55 KB | 6 272 | 2.5 KB | 6.1 KB (`fo`) |
| `case_law` | 16 390 | 1 208 | 58.5 MB | 16.6 MB | 432 952 | 6.4 MB | 2.6 MB (`fo`) |
| `eu` | 43 | 766 | 1.4 MB | 0.4 MB | 51 791 | 14 KB | 50 KB (`fo`) |
| `region` | 10 | 208 | 35 KB | 21 KB | 1 100 | 2.2 KB | 1.2 KB (`fo`) |
| `municipality` | 15 | 110 | 13 KB | 9 KB | 211 | 2.2 KB | 0.4 KB (`st`) |

Every group has body text; the whole index is 78.5 MB (version 1, one index
with `[gap, bits]` postings and every locality column, was 94.0 MB for the
same corpus). Titles and numbers alone would be 2.3 MB for `sfs` and 9.0 MB
for `case_law`. A Nationell search reads the five national groups' document
tables (about 8 MB, mostly case law) once per session, then a few shards per
query.

## Site size budget

GitHub Pages publishes at most 1 GB per site. `api/size_report.py` measures
the built site and fails CI above the budget:

- `api.yml` (pull requests and `main`) checks the API alone;
  `pages.yml` checks the whole site (API and web app) before uploading it.
- Budget 900 MB, warning above 800 MB (MB = 1 000 000 bytes); change them
  with `--budget-mb` and `--warn-mb` or the defaults in the script.
- The report, in the workflow's step summary, lists the total, the size per
  top-level folder, per layer (its listings, its `docs/` files and its search
  group) and per search group with its fields and budget.

Run it locally after a build:
`python3 -I api/size_report.py --api build/api/v1`.

Measured on the full corpus (27 901 documents, built 2026-10-29, API only;
the web app adds about 15 MB):

| | before (search v1) | after (search v2) |
| --- | --- | --- |
| whole API | 676.0 MB | 660.5 MB |
| `docs/` | 552.9 MB | 552.9 MB |
| `search/` | 94.0 MB | 78.5 MB |
| listings (all layer folders) | 29.1 MB | 29.1 MB |

By layer (listings, documents and search group): case law 481.7 MB, SFS
163.2 MB, EU 14.3 MB, the rest under 1 MB each.

Document bodies are 96 % of `docs/` (528 MB of 553 MB), and the JSON is
already compact (no indentation, no spaces after separators, UTF-8 without
`\u` escapes); the null-valued meta keys would save under 5 MB and the
contract keeps them. The rest of the API is too small to matter.

### Approach and headroom

The API stays on GitHub Pages. With search split by layer, a layer that
outgrows its search budget loses only its own body search, and the CI budget
stops a build long before Pages refuses it. At today's size there are about
240 MB of headroom below the 900 MB budget. When the budget gets close (the
full agency, county and municipal runs and amendment history are the expected
growth), the next steps, in order:

1. Lower the search budget of the largest group (case law first), which frees
   up to about 50 MB.
2. Serve case-law bodies from smaller per-year chunks or drop them from
   `docs/<id>.json` (a breaking change: needs a new `api_version`).
3. Move `docs/` to object storage or a CDN (Cloudflare R2, S3) and keep the
   listings, search and web app on Pages.
