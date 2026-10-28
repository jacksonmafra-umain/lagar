# Static JSON API (v1)

The app reads only this API, never the corpus. All files are static JSON served
under `/api/v1/`. All paths below are relative to that prefix.

Conventions:

- JSON is UTF-8. All keys are `snake_case`.
- Dates are `YYYY-MM-DD`. Timestamps are UTC, `YYYY-MM-DDTHH:MM:SSZ`.
- `null` is used for unknown or not-applicable values; keys are never omitted.
- Canonical examples live in `docs/api/examples/` and mirror the paths below.
  They include a series listing (`sfs/ordinance/index-1.json`) and an empty layer
  listing (`eu/index-1.json`: `items: []`, `page_count: 1`, `total: 0`).

## Vocabulary

Layers (fixed order): `fundamental`, `sfs`, `agency`, `case_law`, `eu`,
`region`, `municipality`, `service`.

Types and the layer each belongs to:

| type | layer |
| --- | --- |
| `fundamental_law` | `fundamental` |
| `act` | `sfs` |
| `ordinance` | `sfs` |
| `other_statute` | `sfs` |

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
"other statutes".

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
| `number` | string | no | e.g. `1999:175`; N-series ordinances (published outside the printed SFS) start with `N`, e.g. `N2026:1` |
| `type` | string | no | type id |
| `issued` | string (date) | yes | |
| `repealed` | string (date) | yes | |
| `in_force` | string (date) | yes | entry into force; same value as `meta.in_force` |
| `amended_through` | string | yes | SFS number of the latest amendment, `^N?\d{4}:\d+$`; same value as `meta.amended_through` |
| `ministry` | string | yes | issuing ministry or body; same value as `meta.ministry` |

Keys appear in the order above. `in_force`, `amended_through` and `ministry`
were added within v1: they are always present but may be `null`, and they come
after the original keys. The change is additive, so v1 clients that ignore
unknown keys keep working; clients should treat the three fields as optional
and nullable.

Sort order: `issued` descending, then `number` descending, across pages. `number` is compared numerically by (year, ordinal), not as a string, so `1999:175` comes before `1999:99`. A series prefix (`N`, `RFS`) is ignored for ordering; on a tie the plain number is listed before the prefixed one (`2026:5` before `N2026:5`). Old prints keep Riksdagen's numbering, such as `1827:60 s.1007` or `1899:bih. 25`: non-digits before the ordinal are skipped and the rest after it only breaks ties. Items
with `issued: null` sort after dated ones.

## `GET docs/<id>.json`

| field | type | null | notes |
| --- | --- | --- | --- |
| `meta` | object | no | all frontmatter fields, below |
| `body` | string | no | Markdown: `# <title>`, paragraphs, section numbers as `**1 §**` |

### `meta` fields

`amended_through` is the last amending SFS number according to the source. It
can be set while `amended_by` is empty or partial: `amended_by` lists only the
amending SFS numbers found in the text.

`in_force` and `amendments` come from the SFS register (SFSR) at
<https://rkrattsbaser.gov.se/sfsr>, which only some statutes have been read
from so far. Until then `in_force` is `null` and `amendments` is `null`. Once
read, `amendments` is the register's full list of amending acts, so it is
usually longer than `amended_by`.

Keys are always present, in this order. They mirror the corpus frontmatter
(`docs/schema/frontmatter.schema.json`); `amendments` is the one key the
frontmatter may leave out, and the API then serves it as `null`.

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
| `amended_by` | array of string | no | each `^N?\d{4}:\d+$` (N-series numbers keep their `N`), may be empty |
| `amended_through` | string | yes | SFS number of the latest amendment applied, `^N?\d{4}:\d+$` |
| `reprinted_by` | array of string | no | each `^N?\d{4}:\d+$`, may be empty |
| `ministry` | string | yes | |
| `eli` | string (URI) | yes | |
| `language` | string | no | `sv` or `en` |
| `authoritative` | boolean | no | |
| `source` | string (URI) | no | |
| `source_sha256` | string | no | 64 lowercase hex characters |
| `fetched_at` | string (UTC timestamp) | no | |
| `amendments` | array of amendment | yes | `null` until read from SFSR; `[]` when the register lists none. Added in v1 without a version bump |

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

## Full-text search: `GET search/index.json`, `search/docs.json`, `search/shards/<key>.json`

A static inverted index, added within v1 (additive: no existing file changes).
The client reads the manifest, tokenises the query with the rules below, and
fetches only the shards its terms fall in. Examples: `docs/api/examples/search/`
(built from the API test fixture corpus).

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

### `search/index.json` (manifest)

| field | type | null | notes |
| --- | --- | --- | --- |
| `search_version` | integer | no | currently `1`; bumped on an incompatible format change |
| `built_at` | string (UTC timestamp) | no | same as `index.json`; cache shards and `docs.json` keyed by it, since document numbers change between builds |
| `doc_count` | integer | no | rows in `docs.json` |
| `term_count` | integer | no | distinct terms over all shards |
| `fields` | array of string | no | indexed fields: `title`, `number`, and `body` when the full text fits the budget (below) |
| `field_bits` | object | no | bit per indexed field: `title` 1, `number` 2, `body` 4 |
| `normalization` | object | no | `lowercase`, `fold_from`, `fold_to`, `token_pattern`, `min_length` (2), `keep_single_digits` (true), `stop_words` (sorted) |
| `shard_key_length` | integer | no | `2` |
| `shards` | array of shard | no | sorted by `key`; only keys that have terms |

Shard object: `key` (string), `terms` (integer, terms in the shard) and
`bytes` (integer, size of the shard file).

### `search/docs.json`

`fields` lists the column names (`id`, `title`, `number`, `type`, `issued`,
`repealed`, same values as listing items); `docs` is one row per document,
sorted by `id`. A document's number in the postings is its 0-based row index.

### `search/shards/<key>.json`

`key` is the first two characters of a term, with any character outside
`a-z` and `0-9` replaced by `_` (`skollag` → `sk`, `1962:700` → `19`,
`über` → `_b`). A one-character term (a single digit) has a one-character key,
for example `5`. A shard exists only when the manifest lists its key.

| field | type | null | notes |
| --- | --- | --- | --- |
| `key` | string | no | shard key |
| `terms` | object | no | term → postings, terms sorted |

Postings are a flat integer array of pairs `[gap, bits, gap, bits, ...]`,
by ascending document number. The first `gap` is the document number itself,
each following `gap` is the difference to the previous document. `bits` is
the OR of the `field_bits` the term occurs in for that document (5 = title and
body). Example: `"utgar": [0, 4]` means document 0 has `utgar` in its body.

### Querying

- Exact term: look the term up in its shard.
- Prefix (type-ahead): every term starting with the typed text is in the same
  shard as long as the text has at least two characters, so filter the shard's
  sorted terms by prefix.
- Several terms: intersect the document sets. A suggested rank: documents
  matching in the title first, then number, then body only (lowest bit set),
  then document order. Filters (type, dates, status) apply to `docs.json`
  rows.

### Size budget

Body text is indexed only when the whole index (manifest, `docs.json` and all
shards, uncompressed) stays within 100 MB; otherwise the build falls back to
titles and numbers and `fields` says so. The frontmatter has no summary field
yet, so titles and numbers are the only metadata indexed. Measured on the full
corpus (11 428 documents, built 2026-10-29):

| index | files | uncompressed | gzip (sum per file) | terms | largest shard |
| --- | --- | --- | --- | --- | --- |
| titles + numbers | 349 | 2.4 MB | 0.6 MB | 21 221 | 144 KB (`19`) |
| titles + numbers + body | 1 039 | 22.1 MB | 5.5 MB | 216 691 | 1.1 MB (`fo`) |

Both include `docs.json` (1.7 MB, 0.3 MB gzip). The body index fits, so it is
built: the whole API grows from about 139 MB to 161 MB, far below
the 1 GB GitHub Pages limit; generating it adds about 15 s to the build.
