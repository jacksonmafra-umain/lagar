# Coverage

What the corpus covers, what it does not, and where the numbers come from.
Counts per series are in [PROGRESS.md](PROGRESS.md); which agencies and
sources are processed, and why the others are not, is in [AGENCIES.md](AGENCIES.md). Volume does not prove
completeness: read this file next to those numbers.

## Sources and cut-off

| layer | source | cut-off |
| --- | --- | --- |
| fundamental, SFS | Riksdagen open data, `https://data.riksdagen.se/dokumentlista/?doktyp=sfs` and `https://data.riksdagen.se/dokument/<id>` | 2026-10-27 |
| SFS PDF manifest | `https://svenskforfattningssamling.se/regulations/<year>/index.html` and `/doc/<year><number>.html` | 2026-10-30 (full run, 2018 to 2026: 13,547 PDFs; incremental `sfspdf --rss` in the daily `Sync SFS`) |
| SFS amendment register | `https://rkrattsbaser.gov.se/sfsr?bet=<number>` | 2026-10-30 (every statute in the corpus: 11,200 register pages; the daily `Sync SFS` refreshes the statutes it writes) |
| SÖ treaties | Regeringen.se, `https://www.regeringen.se/sitemap.xml` and the pages under `/rattsliga-dokument/sveriges-internationella-overenskommelser/`, PDFs under `/contentassets/` | 2026-10-30 (full run, every year; weekly `Sync SÖ` since then) |
| agency regulations | Arbetsmiljöverket `https://www.av.se/.../publikationer/foreskrifter/`, Finansinspektionen `https://www.fi.se/sv/vara-register/fffs/forteckning-fffs/`, Transportstyrelsen `https://www.transportstyrelsen.se/.../ts-foreskrifter-i-nummerordning/<year>/`, and the listing pages of MIGRFS, KAMFS, KRFS, KFMFS, KFS and MEMYFS (`collector/lagar/agency_generic.py`) | 2026-10-29 (full run of AFS, FFFS and TSFS: 15, 121 and 622 base regulations); 2026-10-30 (MIGRFS, KAMFS, KRFS, KFMFS, KFS, MEMYFS: 121) |
| EU law | Publications Office Cellar: SPARQL `https://publications.europa.eu/webapi/rdf/sparql` and `https://publications.europa.eu/resource/celex/<CELEX>` (Swedish) | 2026-10-29 (curated list with latest consolidated versions; daily `Sync EU` since then) |
| EU case law | Publications Office Cellar, as for EU law; judgments listed by SPARQL (`cdm:case-law_interpretes_resource_legal`) | 2026-10-30 (judgments interpreting the curated acts; daily `Sync EU` since then) |
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

- `in_force` and `amendments` come from the SFS register (SFSR), read for
  every statute in the corpus (11,200 register pages on 2026-10-30). The
  register has no page for 177 numbers, which keep `in_force: null` and no
  `amendments`: the 170 N-series numbers (N2016 to N2026) and 2010:1460,
  2010:1461, 2012:455, 2015:902, 2016:407, 2017:197 and 2019:1204. The
  register itself has no `Ikraft` for Regeringsformen and for most amendments
  before about 1982.
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
  2018-04 on, the year indexes start in 2018) are all recorded in
  `sources/sfs-pdf-manifest.json` with their SHA-256 (13,547 on 2026-10-30).
  Older acts have no PDF there. The PDF bytes are not stored, and the
  documents stay marked `authoritative: false`; Riksdagen remains the text
  source. `collect.py sfsverify` extracts the PDF text and compares it with the
  corpus text (`sources/sfs-pdf-verification.json`): 635 match, 513 have been
  amended since publication, 104 are repealed, 8 are print-only stubs and 47
  differ (table layouts, words split in the Riksdagen text). 12,240 PDFs are
  amendment acts or other numbers with no document of their own in the corpus.
- SÖ treaties: all 3515 SÖ numbers published on regeringen.se on
  2026-10-30 are in the corpus (`treaty`, `corpus/sfs/treaties/`). Text is
  extracted from the PDFs only for SÖ 2010 onward (298 treaties); 36 of them
  have no usable text layer (35 scanned PDFs, one without a Unicode font map)
  and, like every older treaty, keep the page metadata and the PDF link only.
  The PDFs are recorded in `sources/so-pdf-manifest.json` with size and
  SHA-256; the bytes are not kept. 214 pages repeat an SÖ number already used
  by another page: mostly the same treaty published again (bulk folders such
  as `1994/01/` and `2012/12/`, often with extra PDFs such as reservations or
  succession notes), and a few 1920s pages whose number belongs to a
  different treaty. The page whose URL sorts first keeps the number; the
  extra PDFs and the misnumbered treaties are not in the corpus. 272 pages in
  the section have no SÖ number (declarations of intent and similar) and are
  skipped. `issued` is the date of signature; `in_force` is set only when the
  page states the entry into force. Treaties are kept with
  `authoritative: false`.
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
- EU case law covers only the judgments of the Court of Justice and the
  General Court that Cellar records as interpreting an act of the curated EU
  list: 611 on 2026-10-30, of which 605 are in the corpus in Swedish
  (`eu_judgment`, `corpus/eu/judgments/`). Six are gaps in
  `sources/eu-case-law-manifest.json`: four have no Swedish XHTML or HTML
  manifestation and two (C-45/12, C-244/13) answer content negotiation with
  several Swedish documents (HTTP 300). Orders, Advocate General opinions,
  judgments interpreting other acts and the Civil Service Tribunal are not
  collected. The Swedish text is authentic only in cases conducted in Swedish,
  so the others are stored with `authoritative: false`.
- Case law: 16390 of the 16640 referat and notiser the API listed on
  2026-10-29 are in the corpus; the daily `Sync case law` workflow adds new and
  republished ones. Only the anonymised referat and notiser are collected.
  Rulings the courts publish in full (`DOM_ELLER_BESLUT`, about 760),
  leave-to-appeal and preliminary-ruling notices and all attachments (PDF) are
  left out by design (19 such items appeared in the referat/notis listing). 231
  publications were recorded as failed instead of written: 213 had no report
  reference in the schema's form (mostly older kammarrätt and Marknadsdomstolen
  referat with only a case number), 9 repeat a reference already stored from
  another publication (joined cases published twice, e.g. NJA 2017:88, MÖD
  2025:53), and 9 contain what looks like a personal identity number. The
  kammarrätt referat the courts list without a report reference (76 on
  2026-10-30: KGG 8, KJO 23, KST 42, KSU 3, decided 2000 to 2007) are collected
  since then under the court's abbreviation, decision date and case number,
  such as `KRNJ 2007-01-09 mål nr 1097-06`; a per-court scan that day found no
  other referat or notis without a reference. SFS
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
  on 2026-10-30 `www4.skatteverket.se` answered both robots.txt and the SKVFS
  listing with a WAF "Request Rejected" page, so the series is a gap, #206;
  PTSFS: pts.se serves a Radware bot challenge, #194),
  and the other series are not collected yet (#115).
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
  neither is bypassed, both are gaps.
  Since 2026-10-30 the text of these series comes from their PDFs through
  `collector/lagar/pdftext.py` (pdftotext): the consolidated version where the
  agency publishes one, else the regulation's own PDF; the masthead also gives
  the title where the listing only had the number, and `issued`, `published`
  and `in_force` where the listing had none. 484 of the 494 regulations of
  those 15 series have text; 10 PDFs are scans without a text layer (9 NFS, 1
  KOVFS) and are recorded as such in their bodies.
  Five more series follow the same way on 2026-10-30, with titles, dates and
  text read from their PDFs: CSNFS (63, the consolidated version where CSN
  publishes one, including the annual regleringstal notices), BFNAR (17
  general advice in force), LMFS (14 in force), MTFS (3 in force) and IMYFS
  (1). Five PDFs are scans without a text layer (4 CSNFS, 1 LMFS). Repealed
  regulations listed on the LMFS and MTFS pages, and the predecessor series
  LMVFS and DIFS, are not collected.
  Three more on 2026-10-30, also with text from their PDFs: KVFS (17 base
  regulations, found through Kriminalvården's sitemap because its listing
  needs JavaScript), LIVSFS (39 in force, from Livsmedelsverket's yearly
  tables since 2005) and MYHFS (21 in force and 23 repealed, dated from the
  list or from the regulation that repealed them). Repealed LIVSFS
  regulations (no repeal date on the page), 23 MYHFS ones without a known
  repeal date and the predecessor series SLVFS are not collected.
  Five more on 2026-10-30, also with titles, dates and text from their PDFs:
  DVFS (154 base regulations, one page each in domstol.se's sitemap because
  the register needs JavaScript), FFS (68 in force, from the lists that
  Försvarsmakten's four "Gällande FFS" pages load from the site's content API;
  8 old prints are scans without a text layer), EIFS (34, from Ei's el,
  naturgas and fjärrvärme tables), KBVFS (4) and HSLF-FS (119 of about 155
  base regulations listed on kunskapsguiden.se, read from each agency's site
  with its own robots.txt: Socialstyrelsen 62, Folkhälsomyndigheten 37, TLV 7,
  Rättsmedicinalverket 7, IVO 5 and one joint regulation). HSLF-FS gaps:
  Läkemedelsverket's regulations are not collected (its pages need JavaScript
  and its robots.txt disallows PDFs); about 30 more fail on dead or moved links,
  MFOF's redirects and TLV regulations no longer on TLV's page. Predecessor
  series on kunskapsguiden's list (SOSFS, FoHMFS and others) are not collected.
  [AGENCIES.md](AGENCIES.md) lists every series and
  source with its status.
- Agency series published as a list of PDF links (configured in
  `collector/data/agency-series.json`, read by `ListedAdapter`): RGKFS (6 base
  regulations), RIFS (14), SGU-FS (6), SiSFS (30), TVFS (10), UFS (5), VALFS
  (17) and VRFS (3), as of 2026-10-30: every base regulation linked from the
  agency's regulation page. Amending and repealing regulations are listed in
  `amended_by`; consolidated versions and reprints are linked from the base
  regulation. The text is only in the PDFs (hashed in
  `sources/agency-pdf-manifest.json`, not extracted yet), so the bodies hold
  the number, the title from the link text, the issuer and the PDF links; RIFS,
  UFS and some TVFS links carry only the number, so those documents are titled
  with it. A base regulation whose own PDF is not linked with its number (RGKFS
  2006:1, TVFS 2015:1) is known through its reprint. Older series of the same
  agencies (Revisorsnämnden's RNFS on the RIFS page) are not collected.
- SKSFS (18 base regulations) and SSMFS (41) as of 2026-10-30, the same way.
  Skogsstyrelsen writes numbers as `SKSFS 2011 7` and files every amendment in
  its base regulation's folder; a regulation that replaced another (SKSFS
  2021:1, filed under 1998:2 and in its own folder) is stored as a base
  regulation and also listed in the older one's `amended_by`. SSMFS has one
  page per base regulation in force with the original and consolidated PDFs and
  the amendments.
- ÅFS (Åklagarmyndigheten, 23 base regulations in force) as of 2026-10-30,
  from the cards on its ÅFS page, which give the decision and publication
  dates. The 77 repealed regulations, the 41 notices and the regulations
  numbered in ÅFS that change Riksåklagarens older regulations (`föreskrifter
  (1999:178)`) are not stored. Document ids map `å` to `aa` (`aafs-2023-7`) so
  they do not collide with Arbetsmiljöverket's AFS.
- STAFS (Swedac, 187 base regulations: 37 in force and 150 repealed) as of
  2026-10-30, in full text: Swedac's register `regelverk.swedac.se` publishes
  `foreskrifter.json` (every regulation with dates, the regulation it amends
  and its repeal) and a Markdown file per regulation, the consolidated version
  where there is one. Repealed regulations are stored with `repealed` set; 15
  repealed ones whose repeal date the index does not give are not stored. The
  PDF folder on `www.swedac.se` is disallowed by robots.txt and is not used.
- PFS (Pensionsmyndigheten, 81 base regulations) and PRVFS (Patent- och
  registreringsverket, 17 base regulations in force, from its division A1) as
  of 2026-10-30, with links to the PDFs. Pensionsmyndigheten's page also lists
  regulations of the predecessor series (FKFS, RFFS, PPMFS) still in force;
  only PFS numbers are collected.
- PMFS (Polismyndigheten, 50 regulations in force) and RPSFS (29 regulations of
  the former Rikspolisstyrelsen still in force) as of 2026-10-30, from the four
  pages of Polismyndigheten's list, with entry into force, amendments and the
  consolidated (sammanställd) PDFs. Repealed regulations are only listed
  separately and are not collected.
- SCB-FS (Statistiska centralbyrån, 48 base regulations on reporting duties in
  force) as of 2026-10-30, in full text from SCB's page per regulation. SCB's
  table also lists amending and repealing regulations (44, in `amended_by`).
  The regulations on official statistics are collected from their own page
  (see below).
- UHRFS (Universitets- och högskolerådet, 13 base regulations in force with
  their consolidated PDFs), STEMFS (Energimyndigheten's document archive,
  read at the 10 s crawl delay its robots.txt asks for) and RFS
  (Riksdagsförvaltningen, from Riksdagen's open data `doktyp=rfs`, in full
  text: the consolidated "Fulltext" document where there is one) as of
  2026-10-30. RFS: only base regulations in force are stored; the open data
  marks repealed ones (`Upphävd`) without a repeal date.
- RA-FS (Riksarkivet, general regulations) as of 2026-10-30, from the JSON API
  behind its register `foreskrifter.riksarkivet.se` (`api/rafs/sok`): base
  regulations in force and repealed ones, whose `repealed` date is the entry
  into force of the regulation that repealed them; a repealed regulation whose
  repealing regulation is not in the register is not stored. Riksarkivet's
  agency-specific regulations (RA-MS) are not collected.
- SKOLFS (Skolverket, 965 base regulations in force), SJÖFS (Sjöfartsverket,
  44 base regulations in force from its systematic list) and TRVFS
  (Trafikverket, 42 regulations) as of 2026-10-30. SKOLFS comes from the API
  behind Skolverket's search app (`skolfs.skolverket.se/api`), with decision,
  publication and entry-into-force dates and the latest consolidated PDF;
  expired regulations are not stored (no repeal date). SJÖFS: regulations
  numbered before plain ordinals (`1952:A9`) and rows marked repealed are not
  stored; many of Sjöfartsverket's former regulations now live in TSFS.
  TRVFS: Trafikverket's search form (a POST per year, without speed
  regulations and repealed ones); its road-specific speed regulations
  (hastighetsföreskrifter) and the older VVFS and BVFS series are not
  collected, and Transportstyrelsen's regulations republished there are
  already in TSFS.
- SvKFS (Svenska kraftnät, 6 regulations: 4 in force, 2 repealed in 2022) and
  TFS (Tullverket, 24 base regulations in force, including Inspektionen för
  strategiska produkter's) as of 2026-10-30, in full text from the PDFs.
  SvKFS comes from the JSON document list behind its regulations page. TFS
  comes from Tullverket's document search, a POSTed form; repealed TFS
  regulations carry no date there and are not stored, nor are notices
  (tillkännagivanden). Older consolidated TFS versions are HTML pages and are
  not kept.
- TPPVFS (Pliktverket, TPPVFS 2024:1 and the predecessor's TRMFS 2017:1 and
  2017:4, stored under TRMFS), SIFS (Spelinspektionen, 9 SIFS and 6 of the
  former Lotteriinspektionen's LIFS) and STFS (Sametinget, 13) as of
  2026-10-30, in full text from the PDFs' text layer. Pliktverket's TPPVFS
  2024:1 PDF carries no number in its link; the number was read from the PDF.
  Spelinspektionen's list of regulations in force is itself a PDF; three
  regulations on it (LIFS 2018:3, LIFS 2018:8, SIFS 2019:3) have no page on
  the site and are not collected. Sametinget's document bank is read through
  the JSON its search page uses.
- SCB-FS now also holds SCB's three regulations on official statistics (SCB-FS
  2016:17, 2021:26, 2023:6). The monthly consumer price index notices (KPI)
  are notices of index values, not rules, and are not collected.
- Since 2026-10-30 the PDF-only series above (RGKFS, RIFS, SGU-FS, SiSFS,
  TVFS, UFS, VALFS, VRFS, SKSFS, SSMFS, UHRFS, PFS, ÅFS, PRVFS, PMFS and
  RPSFS, STEMFS, RA-FS, SJÖFS, TRVFS) carry the regulation text read from
  the PDF's text layer. SKOLFS carries the text of each regulation as issued
  (not the consolidated version). Skolverket serves the latest consolidated
  version of SKOLFS 2011:22 as a Word file instead of a PDF; it is noted in the
  manifest and not linked.
- PTSFS (Post- och telestyrelsen) is a gap: on 2026-10-30 pts.se answered its
  regulation library with a Radware bot-verification page (#194).
- SJVFS (Statens jordbruksverk) is a gap: its regulations are PDFs on
  `jvdoc.sharepoint.com`, whose robots.txt disallows every path, and
  Jordbruksverket's search page lists only the first 50 of its 341 base
  regulations without JavaScript (checked 2026-10-30, #202).
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
- Municipal regulations: every kommun with an entry in
  `collector/data/municipalities.json` is collected in full; kommuner without an
  entry are not collected yet, and there is no known target (roughly 30–150
  documents per kommun). Scope decision: only rules that bind residents are collected (lokala
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
  - Malå, Storuman and Åsele publish part of their taxor and hälsoskydd rules only as
    HTML pages, which the PDF listings do not cover; Lycksele's lokala
    ordningsföreskrifter PDF was not found. Nordmaling, Norsjö, Malå, Storuman,
    Sorsele, Lycksele and Arjeplog mix resident rules and internal documents on one
    page without headings, so their configs keep only listed file names; a new
    document with another name is not picked up until the config is updated.
  - Karlstad serves its files only
    through time-limited SharePoint links on a host whose robots.txt disallows
    everything, so it is not collected.
  - Skövde: the taxor och avgifter page and the five lokala föreskrifter
    (ordnings-, avfalls-, hälsoskydds- and torghandelsföreskrifter and ABVA),
    which its författningssamling lists only as JSON in the Next.js page's
    script data (read with `embedded: "next"`), are collected. Nora
    publishes only three taxor as PDFs (bygglov, VA, avfall); no ordnings-,
    avfalls- or hälsoskyddsföreskrifter were found on its site. Arvika's taxor
    page and Älvsbyn's föreskrifter (no index page) are not covered.
  - Boden's taxor pages and Örnsköldsvik's, Sandviken's and Tidaholm's topic
    pages hold rules that the configured listings do not cover; Kiruna covers
    its föreskrifter and bygglovstaxa only.
  - Trelleborg: robots.txt disallows `/app/uploads/`, where every PDF lives, so
    the PDFs are never fetched; the documents point at the listing page and are
    recorded as gaps in the manifest. Its taxor page lists no PDFs.
  - Ystad's taxor section of the författningssamling is empty on the page; only
    section A (allmänna föreskrifter) is collected. Lund links two of its avgifter
    as HTML pages, which are not collected. Ängelholm covers its lokala
    ordningsregler page only.
  - Helsingborg publishes its författningssamling on styrning.helsingborg.se
    (PDFs on media.helsingborg.se); its föreskrifter page and the two avgifter
    PDFs are collected. Its avfallstaxa lives on NSR's site and its environment
    fees on a separate site for companies; neither is collected.
  - Båstad's "Regler och styrande dokument" page (under Kommunfakta) lists its
    författningssamling as one Sitevision file list; its 29 föreskrifter and
    taxor are collected, internal documents left out by title.
  - Perstorp: its "Kommunal författningssamling" page keeps the document list in
    a minimised layout that opens only through `?sv.state=normal`, which
    robots.txt disallows, and the site has no sitemap. Not bypassed; a gap.
  - Lomma publishes its författningssamling in a Netpublicator reader; its channels
    E (lokala föreskrifter) and F (taxor) are read through Netpublicator's public
    API (`json_list` with `follow_items`). Vellinge publishes its lokala
    ordningsföreskrifter and hälsoskyddsföreskrifter as web pages, collected as
    page text (`html_pages` over its gzipped sitemap).
  - Not collected in Skåne, with the reason per kommun in `AGENCIES.md`: Östra
    Göinge and Höör (Ciceron meeting portals). Their issues stay open.
  - Staffanstorp: robots.txt disallows `/app/uploads/`, where every PDF lives, so
    the PDFs are never fetched; the documents point at the listing page and are
    recorded as gaps in the manifest.
  - Simrishamn publishes its taxor as HTML text on its taxor page, which is not
    collected; only the allmänna lokala ordningsföreskrifter are a PDF.
  - Tanum publishes its rules as web pages in an A–Z list; they are collected as
    page text (`html_pages`), the ABVA as its PDF. The avfallsföreskrifter page
    refers to Rambo AB's site for the full text.
  - Härryda has no författningssamling or list of its rules. Its avgifter och
    taxor page links to topic pages, collected as page text (`html_pages`) or as
    the taxa PDF a page links; the VA and avfall taxor and the avfallsföreskrifter
    come as PDFs from the pages of Härryda Vatten och Avfall AB (hvaa.se), the
    current versions only; library fees and hall hire are left out, and no lokala
    ordningsföreskrifter were found on either site: 13 documents (2026-10-30).
- Kommuner checked and not collected are listed with the reason in `AGENCIES.md`
  (curated in the `kommuner` section of `collector/data/agencies.json`):
  - Karlskrona (1080): www.karlskrona.se answers every request, robots.txt
    included, with an HTTP 403 "Åtkomst nekad" bot-check page; not bypassed.
  - Not collected yet, with the reason per kommun in `AGENCIES.md`: Värnamo
    (its DocumentWeb host did not answer; retried 2026-10-31), Mönsterås (site
    did not answer; retried 2026-10-31) and Linköping (rules on Google Drive;
    waits for an owner decision). Their issues stay open.
  - Collected through platform adapters: Lidingö and Västervik (Evolution
    DocumentWeb API), Sigtuna (Netpublicator), Gotland (its document service),
    Vallentuna (gzipped sitemap of the file-share module), Uppsala (sitemap and
    the rule pages' own titles), Torsås (titles from table rows) and Aneby and
    Jönköping (curated topic pages; Jönköping's avfall rules are on
    juneavfall.se and not collected).
    Östhammar's robots.txt shuts named AI crawlers out of its rule pages but
    allows this collector's agent; the owner approved collecting it.
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
