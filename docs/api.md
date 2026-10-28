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
| `case_report`, `case_notice` | report reference: `NJA 2019 s. 2`, `HFD 2020 ref. 5`, `HFD 2020 not. 3`, `NJA 2004 N 23`, `MIG 2026:10`, `AD 2020 nr 45` | none: `amended_by` and `reprinted_by` are `[]`, `amended_through` is `null` |
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

Keys appear in the order above. `in_force`, `amended_through` and `ministry`
were added within v1: they are always present but may be `null`, and they come
after the original keys. The change is additive, so v1 clients that ignore
unknown keys keep working; clients should treat the three fields as optional
and nullable.

Sort order: `issued` descending, then `number` descending, across pages. `number` is compared numerically by (year, ordinal), not as a string, so `1999:175` comes before `1999:99`. A series prefix (`N`, `RFS`) is ignored for ordering; on a tie the plain number is listed before the prefixed one (`2026:5` before `N2026:5`). Old prints keep Riksdagen's numbering, such as `1827:60 s.1007` or `1899:bih. 25`: non-digits before the ordinal are skipped and the rest after it only breaks ties. Items
with `issued: null` sort after dated ones.

The other layers' numbers are also compared by (year, ordinal), descending:

- `agency_regulation`, `county_regulation`: year and ordinal after the series
  (`AFS 2023:10` before `AFS 2023:9`); on a tie the series name descending.
- `case_report`, `case_notice`: year and the number after it, which is the
  page for `NJA … s.` and the report or notice number otherwise; on a tie the
  report series descending.
- EU types: the act's year and number. `(EU) 2016/679` is year/number; with
  `nr`, `(EG) nr 1907/2006` and `(EEG) nr 1408/71` are number/year; directives
  and decisions such as `95/46/EG` and `2004/18/EG` are year/number. A
  two-digit year is 19xx.
- `municipal_regulation`: the first year (1600–2099) in the number and the
  digits that follow it (`SKFS 2024:12` is (2024, 12)); a number without a
  year sorts as (0, 0), after the others; ties by the full number.

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
