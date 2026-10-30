# Coverage

What the corpus covers, what it does not, and where the numbers come from.
Counts per series are in [PROGRESS.md](PROGRESS.md); which agencies and
sources are processed, and why the others are not, is in [AGENCIES.md](AGENCIES.md). Volume does not prove
completeness: read this file next to those numbers.

## Sources and cut-off

| layer | source | cut-off |
| --- | --- | --- |
| fundamental, SFS | Riksdagen open data, `https://data.riksdagen.se/dokumentlista/?doktyp=sfs` and `https://data.riksdagen.se/dokument/<id>` | 2026-10-27 |
| SFS PDF manifest | `https://svenskforfattningssamling.se/regulations/<year>/index.html` and `/doc/<year><number>.html` | 2026-10-28 (sample) |
| SFS amendment register | `https://rkrattsbaser.gov.se/sfsr?bet=<number>` | 2026-10-28 (pilot: 1974:152, 1962:700, 1998:808) |
| agency regulations | Arbetsmiljöverket `https://www.av.se/.../publikationer/foreskrifter/`, Finansinspektionen `https://www.fi.se/sv/vara-register/fffs/forteckning-fffs/`, Transportstyrelsen `https://www.transportstyrelsen.se/.../ts-foreskrifter-i-nummerordning/<year>/`, and the listing pages of MIGRFS, KAMFS, KRFS, KFMFS, KFS and MEMYFS (`collector/lagar/agency_generic.py`) | 2026-10-29 (full run of AFS, FFFS and TSFS: 15, 121 and 622 base regulations); 2026-10-30 (MIGRFS, KAMFS, KRFS, KFMFS, KFS, MEMYFS: 121) |
| EU law | Publications Office Cellar: SPARQL `https://publications.europa.eu/webapi/rdf/sparql` and `https://publications.europa.eu/resource/celex/<CELEX>` (Swedish) | 2026-10-29 (curated list with latest consolidated versions; daily `Sync EU` since then) |
| regional (county) | Länsstyrelserna, `https://www.lansstyrelsen.se`: the 21 landing pages in `collector/data/counties.json`, their year index and detail pages (Stockholm, Halland, Gävleborg), PDF links, file-share modules and year folders (the other 18) | 2026-10-29 (2025–2026, all 21 counties) |
| case law | Sveriges Domstolar, `https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar` (referat and notiser) | 2026-10-29 (full run: publications up to 2026-10-28; daily sync from then on) |
| municipal regulations | Stockholm `https://start.stockholm/om-stockholms-stad/politik-och-demokrati/styrdokument/kommunal-forfattningssamling/`, Göteborg Domino view `https://www4.goteborg.se/prod/Stadsledningskontoret/LIS/Verksamhetshandbok/Forfattn.nsf/vyHandBok`, Malmö `https://malmo.se/Om-Malmo-stad/Demokrati-och-politik/Sa-styrs-Malmo/Forfattningssamling/` (citizen rules and taxor pages) | 2026-10-29 (sample: five documents per kommun) |

The SFS target (11567 documents) is the number Riksdagen lists for document
type `sfs` on that date, all statute types together.

The regional target (630 documents) is the number of numbered regulations the
21 county landing pages (and their year indexes and folders) list for 2025 and
2026 on 2026-10-29; it covers only those two years.

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
  acts, 70 documents: 40 Official Journal texts and 30 latest consolidated
  versions); its target is that list, not the roughly 47,000 acts in force.
  Three acts have Swedish only as PDF or print in the Cellar: REACH (32006R1907),
  Regulation (EC) No 883/2004 (32004R0883) and Directive 2004/38/EC (32004L0038).
  They are recorded as gaps in `sources/eu-manifest.json`; their consolidated
  versions are in the corpus. Consolidated versions have no legal effect
  (`authoritative: false`). Eleven acts that were never amended, only corrected,
  have no Swedish consolidated expression (the DSA, the Data Act, the Data
  Governance Act, DORA, the platform-to-business regulation, Rome II and the
  working-time, services, copyright, transparent-working-conditions and
  minimum-wage directives); their Official Journal text is current and the
  manifest records the consolidation as a gap. The decisions 2011/833/EU and
  (EU) 2022/2481 have no consolidated version. `amended_through` is set on
  consolidated versions that apply at least one amending act (23 of 30); the
  Official Journal texts keep it `null`. Rows of a table nested inside another
  table's cell stay on one line, and the `M1`, `M2` … labels of a consolidated
  text's amendment list are dropped with the other modification markers.
- Case law: 16390 of the 16640 referat and notiser the API listed on
  2026-10-29 are in the corpus; the daily `Sync case law` workflow adds new and
  republished ones. Only the anonymised referat and notiser are collected.
  Rulings the courts publish in full (`DOM_ELLER_BESLUT`, about 760),
  leave-to-appeal and preliminary-ruling notices and all attachments (PDF) are
  left out by design (19 such items appeared in the referat/notis listing). 231
  publications are recorded as failed instead of written: 213 have no report
  reference in the schema's form (mostly older kammarrätt and Marknadsdomstolen
  referat with only a case number), 9 repeat a reference already stored from
  another publication (joined cases published twice, e.g. NJA 2017:88, MÖD
  2025:53), and 9 contain what looks like a personal identity number. SFS
  references (`lagrumLista`) stay plain text in the body; the app's reader links
  the citation forms to the SFS documents the API publishes.
- Agency regulations: three of about 100 series (lagrummet.se lists them) are
  collected, in full as of 2026-10-29: every base regulation in force of AFS
  (15) and FFFS (121), and every TSFS base regulation on Transportstyrelsen's
  year listings (622: 331 in force and 291 repealed, stored with `repealed`
  set). The targets in `collector/data/targets.json` are those counts. Only
  base regulations are stored; amending regulations (30 AFS repealing
  regulations, 280 FFFS and 1528 TSFS amending or repealing regulations) are
  not stored on their own but listed in `amended_by`. No regulation failed and
  no host blocked the run. Transportstyrelsen's number-order index also lists
  regulations of the predecessor series it took over (LFS, JvSFS and others,
  years 1978 to 2008 and later), some still in force; only numbers in the TSFS
  series are collected, so those are a gap. The earliest TSFS base regulation
  in the corpus is TSFS 2009:1. AFS has the consolidated text from
  Arbetsmiljöverket's HTML pages. FFFS and TSFS publish the text only as PDF:
  their bodies hold metadata, the agency's summary and links to the PDFs,
  whose SHA-256 is in `sources/agency-pdf-manifest.json`; PDF text is not
  extracted (owner decision: no non-stdlib dependency). `issued` is known only
  for unamended AFS regulations, and AFS `in_force` only for those; FFFS and
  TSFS have no decision date on their pages. Arbetsmiljöverket's robots.txt
  disallows its folder of original PDFs, which is never requested. Boverket
  (BFS, API key probably needed; not signed up for now), Skatteverket (SKVFS:
  an earlier robots.txt request was rejected by a WAF, on 2026-10-29 it
  answered normally) and the other series are not collected yet (#115).
  Six more series are collected as of 2026-10-30 through the generic link-list
  adapter, every base regulation their agencies list: MIGRFS (21 in force),
  KAMFS (74, in force and earlier ones), KRFS (12), KFMFS (6), KFS (4) and
  MEMYFS (4). Each agency publishes the text only as PDF, so their bodies hold
  the title, the amending regulations named on the listing and links to the
  PDFs (SHA-256 in `sources/agency-pdf-manifest.json`); the text will follow
  through the shared PDF text helper. Titles come from the listings; dates are
  not on them, so `issued` and `in_force` are null.
  Eleven more series follow on 2026-10-30: NFS (164 of the 166 base
  regulation pages in Naturvårdsverket's sitemap, in force and repealed, with
  `repealed` set where the page says so; NFS 2000:2 and NFS 2001:20 do not
  name their number), FKFS (147 in force, with dates from Försäkringskassan's
  register; three old ones are Word files, not hashed), KOVFS (22), HVMFS
  (21), MCFFS (11), AFFS (9), MDFFS (6), AGVFS (5), ELSÄK-FS (3), KIFS (3) and
  IAFFS (3). AFFS and MDFFS publish the full text as HTML and have it; the
  others publish the text only as PDF. Predecessor series listed on the same
  pages (RFFS, MSBFS, FIFS, AMSFS) are not collected. Bolagsverket (BOLFS)
  answers with a bot check and Konkurrensverket (KKVFS) with 403 Forbidden;
  neither is bypassed, both are gaps. [AGENCIES.md](AGENCIES.md) lists every series and
  source with its status.
- Public services have no collector yet; what the Tjänster tab should hold is
  an open owner decision.
- Regional regulations: 2025 and 2026 are collected for all 21 counties (630
  regulations); earlier years are not collected yet. Only Stockholm, Halland and
  Gävleborg publish each regulation as an HTML page, so only their documents
  carry the text (taken from that page). The other 18 counties publish only the
  printed PDF; their documents hold the number, the title from the link text or
  file name, the issuer and a link to the PDF, and say that the text is only in
  the PDF. Their `issued` is null except in Dalarna, whose list gives the
  decision date (32 of 34). Västerbotten's file names and two of Dalarna's entries carry no
  title, so those documents are titled with the number. PDFs are recorded by URL
  and SHA-256 but never parsed. Files without a recognisable number are not
  collected: registers of rules in force, Östergötland's four unnumbered fire-ban
  and water-protection files of 2026 and one of 2025, and Uppsala's file printed
  as "03FS 20026_11" (03FS 2026:11). Files sharing a number, such as a
  regulation and its map in Norrbotten, form one document. `repealed` and
  amendment links are not filled (the sites publish no status; a regulation the
  county marks "UPPHÄVD" gets a note in the body), and `in_force` only when an
  HTML text names one date. Local traffic regulations (Transportstyrelsen's STFS)
  and the self-governing regions are out of scope.
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
- Public services have no collector yet and no known target.

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
