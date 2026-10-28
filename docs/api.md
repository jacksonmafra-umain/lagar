# Static JSON API (v1)

The app reads only this API, never the corpus. All files are static JSON served
under `/api/v1/`. All paths below are relative to that prefix.

Conventions:

- JSON is UTF-8. All keys are `snake_case`.
- Dates are `YYYY-MM-DD`. Timestamps are UTC, `YYYY-MM-DDTHH:MM:SSZ`.
- `null` is used for unknown or not-applicable values; keys are never omitted.
- Canonical examples live in `docs/api/examples/` and mirror the paths below.

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

Sort order: `issued` descending, then `number` descending, across pages. `number` is compared numerically by (year, ordinal), not as a string, so `1999:175` comes before `1999:99`. A leading `N` is ignored for ordering; on a tie the plain number is listed before the N-series one (`2026:5` before `N2026:5`). Items
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

Keys are always present, in this order. They mirror the corpus frontmatter
(`docs/schema/frontmatter.schema.json`).

| field | type | null | notes |
| --- | --- | --- | --- |
| `id` | string | no | `^[a-z0-9_]+-[0-9a-z-]+$` |
| `title` | string | no | |
| `type` | string | no | one of the types above |
| `layer` | string | no | one of the layers; must equal the layer of `type` |
| `number` | string | no | |
| `issued` | string (date) | yes | |
| `in_force` | string (date) | yes | |
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
