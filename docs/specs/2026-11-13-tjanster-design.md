# Tjänster (services) design

Date: 2026-11-13
Status: draft
Issue: #792
Plan: [`docs/plans/2026-11-13-tjanster.md`](../plans/2026-11-13-tjanster.md)

## Intent

The fourth tab of the app, Tjänster, is a placeholder today. It becomes a catalogue of **public services**: the things a person or a business does with a public body (apply for parental benefit, register a sole-trader business, renew a passport, apply for a building permit), each linked to **the norms it is based on**. A reader who opens a law can see which services apply it, and a reader who opens a service can see, and open, the law behind it. That cross-link between the service and its legal basis is what lagar adds; agency websites already describe their own services, but rarely say which statute they rest on, and never link to it.

lagar does not perform the service. Every service links out to the responsible body's own page, where the person signs in and applies.

## Decisions

The owner chose the master spec's meaning of a service (2026-11-13). The rest are design calls made in this document for the owner to check; each one is marked *(call)*.

### What a service is

A service is an official procedure offered by a Swedish public body (state agency, region, kommun) or a joint public portal (verksamt.se, 1177), described on an official page, and based on at least one norm in the corpus.

Not services, and out of this design:

- **Kungörelser and official notices** (Post- och Inrikes Tidningar, kommun notice boards). `docs/architecture.md` describes layer 9 as notices and gazettes; that line is corrected to match this design.
- **Deadlines and reminders** (tax return dates, benefit periods). They need dates per person and notifications, which an anonymous app without accounts cannot keep in a useful way.
- Private services, even when regulated (banks, insurers, driving schools).

### Corpus

- New type `public_service`, layer `service` (already in the layer vocabulary and the schema enum), corpus folder `corpus/services/`, one file per service. File name and id: `service-<slug>`, with a Swedish ASCII slug of the service name (`service-foraldrapenning-ansokan`) *(call)*.
- The base frontmatter fields keep their meaning where they fit and are `null` or `[]` where they do not: `number` is the slug, `issued`, `in_force`, `repealed`, `amended_through`, `ministry`, `eli` are `null`, `amended_by` and `reprinted_by` are `[]`, `language` is `sv`, `authoritative` is `false`, `source` is the official page, `source_sha256` and `fetched_at` come from the last fetch, `issuer` is the responsible body's name as it writes it.
- New fields, `null` on every other type *(call)*:

| field | type | notes |
| --- | --- | --- |
| `based_on` | array of document id | required and non-empty for `public_service`; every id must exist in the corpus |
| `audience` | array of `private`, `business` | who the service is for |
| `topics` | array, closed vocabulary | life-event topics: `family`, `work`, `business`, `housing`, `health`, `tax`, `vehicles`, `education`, `migration`, `social_support`, `environment`, `legal` |
| `channels` | array of `online`, `form`, `phone`, `office` | how the service can be used, as the official page says |
| `service_url` | URI or null | the page where the service starts (an e-service), when it differs from `source` |
| `issuer_org_number` | string or null | organisation number of the responsible body (SCB Myndighetsregistret for agencies) |
| `scope` | `national`, `region`, `municipality` | who offers it; `region_code` and `municipality_code` keep their existing meaning |
| `template` | boolean | `true` for a service every kommun or region must offer (see below) |

- **Body:** a heading, the lead paragraph of the official page as published (Swedish, at most a few sentences) and a link to the page. Never the whole page, never a rewrite, never a translation *(call)*. Agency web texts are not covered by the copyright exception for statutes and decisions (URL 9 §), so lagar keeps only the short lead and points to the source.
- **The audit** checks that every `based_on` id exists and that `based_on` is non-empty for `public_service`; a broken link is a schema error, so the sync cannot merge it.

### Sources

Every source is official, its `robots.txt` is honoured, requests are rate-limited (at least 1 s) and carry the project User-Agent; a page that blocks automation is a recorded gap, as in the other collectors.

- **The curated list** `collector/data/services.json` is the source of truth for which services exist and what they are based on, like `collector/data/eu-acts.json` for EU acts. Each entry has the slug, the Swedish title, the issuer, `source`, `service_url`, `audience`, `topics`, `scope` and `based_on`. `based_on` is curated by hand, from the official page's own legal references where it gives them; it is never inferred by a model *(call)*.
- **The collector** reads each listed page, records HTTP status, title, lead paragraph, `Last-Modified` and SHA-256 in the committed manifest `sources/services-manifest.json`, and writes the corpus file. A page that is gone or has moved is reported in the run summary and in the statistics, not silently dropped.
- **Seed set** *(call)*, about 60 services, in this order:
  1. The procedures every EU country must offer online under the Single Digital Gateway regulation (EU) 2018/1724, Annex II, as Sweden publishes them. The spike (plan task 1) checks whether the Commission's link repository API returns Sweden's links without a key; if it does, it seeds the list, and a weekly check reports Swedish links that are not yet listed.
  2. The services people use most from Skatteverket, Försäkringskassan, CSN, Transportstyrelsen, Migrationsverket, Arbetsförmedlingen and Polismyndigheten (passport, ID card).
  3. verksamt.se for starting and running a business (Bolagsverket, Skatteverket and Tillväxtverket's joint portal).
- **Agencies blocked for the regulation collectors** (Skatteverket, Bolagsverket and others in `AGENCIES.md`) may still allow their service pages; the spike checks each host's `robots.txt` before any entry is added.

### Scopes

- **Nationell:** services with `scope: national`, always shown.
- **Kommun:** *template services*, one corpus file per kind of service that the law obliges every kommun to offer (bygglov under PBL, försörjningsstöd under SoL, förskola under skollagen, hemtjänst, parkeringstillstånd för rörelsehindrade, avfallshämtning). `template: true`, `scope: municipality`, `municipality_code: null`. The app shows them with the selected kommun's name and links to that kommun's website from `collector/data/kommuner.json`, not to a deep link: 290 kommuner run 290 different sites, and deep links would rot faster than a weekly sync can repair them *(call)*. Kommun-specific deep links are a later step, kommun by kommun, if the template version proves useful.
- **Region:** the same template approach for what every region must offer (healthcare under hälso- och sjukvårdslagen, with 1177 as the joint official entry point, and färdtjänst where the region runs it).
- Services are not a normative layer in the legal sense; they sit at display level 9 in the flag-yellow `service` colour of `DESIGN.md`, below the norms they are based on.

### API

Additive within v1, as with the earlier additions:

- `service/index-<page>.json` and `service/public_service/index-<page>.json`: the existing listing shape.
- `docs/service-<slug>.json`: the existing document shape; the new frontmatter fields are added to `meta` for every document, `null` where they do not apply.
- `service/catalog.json` *(call)*: every service in one file (a few hundred at most) with `id`, `title`, `issuer`, `audience`, `topics`, `channels`, `scope`, `template`, `region_code`, `municipality_code`, `source`, `service_url` and `based_on` resolved to `{id, title, type, layer}`. The tab reads this one file and filters on the device, so it needs no per-topic listings.
- `service/by-norm/index.json`: a map from document id to the ids of the services based on it, for the reader's "Tjänster" section. Only norms with at least one service are keys.
- Search: services join the search index as their own group, so a search for "föräldrapenning" finds the service as well as the law.

### App screens

- **Tjänster home** (the tab): a search field that filters the catalogue, topic chips, a Privatperson / Företag switch, and a list of service cards (title, issuer, a scope badge). It follows the scope chip in the top bar: national services always, and the template services of the selected region and kommun with their name. Empty state when a filter matches nothing.
- **Service detail** (pushed): title, issuer, the lead paragraph, channels, a primary button "Gå till tjänsten" that opens `service_url` (or `source`) in the system browser, "Bygger på" with the norms as layer-coloured rows that open the reader, the fetch date and a note that lagar is not the authority and the official page applies.
- **Reader:** a "Tjänster" section below the table of contents when `service/by-norm/index.json` lists the document.
- **Sparade:** services can be bookmarked like documents.
- **Hierarki:** the service level opens the Tjänster tab.

Layouts follow `DESIGN.md` (glass tiers, the `service` layer colour with its `text` token for text). There is no Stitch screen for services; the Brazilian layouts are references for cards and chips only.

### i18n

- All chrome is in Compose resources, English in `values/`, Swedish in `values-sv/`: tab, filters, topic and audience labels, buttons, the disclaimer, empty states.
- Service titles and lead paragraphs are Swedish as the body publishes them, also in the English UI. No machine translation. An official English page is not used in v1 *(call)*.

## Non-goals

- Accounts, BankID, signing in or filling in anything inside lagar (owner decision: the app is anonymous).
- Performing a service or proxying an agency's e-service.
- Deadlines, reminders, notifications, personal eligibility checks or benefit calculators.
- Kungörelser and official notices.
- Machine-translated service text, and service text rewritten in lagar's words.
- `based_on` links guessed by a model or from text similarity.

## Anti-goals

The tab fails, even if it works, when:

- a service links to a norm that does not apply it, or to a repealed version without saying so;
- a link sends a person to a dead or unofficial page;
- the app looks like the authority itself, so a person thinks they applied when they only read about it.

## Left to the builder

- The exact slug rules and topic assignments, within the vocabulary above.
- Card, chip and detail layouts within `DESIGN.md`.
- How the collector finds the lead paragraph on each host (meta description or first paragraph), per host, tested on saved pages.
