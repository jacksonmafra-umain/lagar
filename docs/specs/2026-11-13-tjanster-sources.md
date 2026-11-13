# Tjänster service sources

Date: 2026-11-13
Status: findings of the source spike (plan task 1, issue #794)
Design: [`2026-11-13-tjanster-design.md`](2026-11-13-tjanster-design.md)
Seed list: [`collector/data/services.json`](../../collector/data/services.json)

This note records what the official service sources allow, what the Single Digital Gateway link repository gives, and how the draft seed list was built. Every request was made with the project User-Agent, at least 1.5 s apart per host (10 s for boverket.se, which asks for it), on 2026-11-13.

## Host verdicts

`robots.txt` was read for every seed host. "Service pages allowed" means the information pages a collector would read (benefit, permit and procedure pages) are not disallowed for `User-agent: *`. A sample of service pages was then fetched from each host to look for bot checks.

| host | robots.txt | service pages allowed | sample fetch | notes |
| --- | --- | --- | --- | --- |
| www.skatteverket.se | 200, only print views, bookmarks and session parameters disallowed | yes | 200, server-rendered | `www4.skatteverket.se` (Rättslig vägledning, linked from every "Rättsinformation" box) still answers robots.txt and pages with a WAF "Request Rejected" page; already recorded for SKVFS in `collector/data/agencies.json`. Not bypassed. |
| www.forsakringskassan.se | 200, Mina sidor, logged-in e-services and `/lank/` disallowed | yes | 200, server-rendered | Sitemap at `/sitemap1.xml.gz`. The vägledningar PDFs under `/download/` are allowed. |
| www.csn.se | 200, SiteVision defaults plus `/kontakta-oss/*`, `/mina-sidor-mobil/*`, login pages | yes | 200, server-rendered | Sitemap at `/sitemap1.xml.gz`. |
| www.transportstyrelsen.se | 200, no disallow rules | yes | 200, server-rendered | Sitemap at `/sitemap.xml`. |
| www.migrationsverket.se | 200, SiteVision defaults plus `/e-tjanster/`, `/lankade-moduler/`, `/webbfunktion/`, search | yes | 200, server-rendered | The e-services themselves (`/e-tjanster/`) are disallowed; the information pages are not. |
| arbetsformedlingen.se | `/robots.txt` redirects to a SiteVision download that serves the file (200) | yes | 200, server-rendered | `/for-arbetsgivare/anstall-med-stod/ansokan-om-nystartsjobb*` and `/hitta-yrken*` disallowed. The `sitemap-www.xml` it lists is empty. |
| polisen.se | 200, `Disallow:` (nothing) | yes | 200, server-rendered | Sitemap at `/sitemap.xml`. |
| verksamt.se | 200, only `/mina-sidor/` and `/inloggad/` disallowed | yes, but see note | 200, empty shell | Every page returns the same client-rendered shell (title "Myndigheternas guide till dig som startar och driver företag", body "Innehåll laddas"); title, lead and legal references load by JavaScript. A collector without a browser cannot read them. Not a block, so not recorded as a gap; verksamt.se services stay out of the seed until the collector task decides how to read them. |
| www.1177.se | 200, `/episerver/`, `/util/`, `/modules/`, `/swagger/`, `/error/`, `/lankbiblioteket/`, `?productid=` disallowed | yes | 200, server-rendered | Law pages name laws (abortlagen, smittskyddslagen) without SFS numbers. 1177 content is regional healthcare, so it belongs to the region template services, not to this national seed. |
| www.boverket.se | 200, `Crawl-delay: 10`, search, sitemap pages and some query parameters disallowed | yes | 200, server-rendered | Honour the 10 s crawl delay. Boverket is a reference for the kommun templates (PBL, bygglov), not a national service host. |

No seed host forbids automation in `robots.txt` and none answered the sample with a bot check, so no gap was added to `collector/data/agencies.json`. The one block met, `www4.skatteverket.se`, is already recorded there.

## Single Digital Gateway link repository

- The Commission's specification at the URL in the plan (`Link repository APIs_08_01_2024.pdf`) now returns 404. The newer copy on single-market-economy.ec.europa.eu answered with a 429 bot challenge page; it was not retried or bypassed. What follows is from the endpoint itself and from the published specification as indexed by search engines.
- The dataset endpoint is `https://webgate.ec.europa.eu/youreurope/sdg/public/dtx/getlinksdataset` (acceptance: `webgate.acceptance.ec.europa.eu`). It returns the whole dataset in one call.
- Three requests were made. `GET` returns 405 "Method 'GET' is not supported". An empty `POST` returns 400 `{"status":400,"errors":"Missing request header 'x-api-key'"}`.
- The specification makes two headers mandatory: `x-api-key`, issued per member state from the API Key module of the SDG application, and `x-api-user`, a valid SDG user of the same country. Sweden's national coordinator for the SDG is Myndigheten för digital förvaltning (Digg).
- Fields per link, from the specification's sample response: `url`, `title`, `description`, `country`, `type` (for example "Procedure"), `urlType`, `status`, `owner`, `createdBy` and metadata.

**Finding:** the link repository does **not** return Sweden's links without a key, and keys go only to member-state SDG users. lagar cannot use it as a source without Digg's cooperation. The seed list was therefore built from the agencies' own pages, and the weekly "Swedish links not yet listed" check in the design is not possible for now. Asking Digg for read access is an owner decision.

Skatteverket's pages carry an "SDG-feedback" block, a sign that the agencies mark their own SDG procedure pages. Without the repository, Annex II coverage was approximated from the agencies' pages: the seed includes student finance, residence permits, driving licence, and parental and sickness benefits; registration of address (flyttanmälan) is left out below for want of a stated basis.

## How `based_on` was taken

`based_on` lists only acts that the responsible body itself names as the basis, in this order of preference:

1. The service page, or a page it links for the same service (Polisen's FAQ, Skatteverket's "Rättsinformation" box), citing the act with or without its SFS number. An act named without a number ("lagen om personnamn", "vapenlagen") is mapped to the act in force with that title; when the agency cites the number elsewhere (vapenlagen (2026:408) on Polisen's begagnade-varor page) that number is used.
2. The agency's own legal-basis document for the benefit: Försäkringskassan's vägledning for each benefit, which states the chapters of socialförsäkringsbalken (and the ordinance) that govern it.
3. The agency's own page on the laws it applies, where it says what each act covers: CSN's "Lagar" and "Förordningar" pages, Migrationsverket's "Lagar och förordningar som styr Migrationsverkets arbete", Transportstyrelsen's "Regler som styr" for körkort.

Every id was checked against the corpus frontmatter (`id`, `number`, `repealed`); none is repealed. Two references on official pages were stale and are handled below: Migrationsverket's law list still names LMA (1994:137, repealed 2026-10-01) and förordning 1984:890 (repealed 2026-01-01).

The `title` in `services.json` is a short service name in the agency's wording; the collector records the page's own title. `service_url` is `null` throughout: no e-service start page was verified in this spike. Every `source` returned 200 without a redirect on 2026-11-13.

## Seed list (58 services)

| slug | issuer | based_on | evidence |
| --- | --- | --- | --- |
| `foraldrapenning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbaae/1782889632400/foraldrapenning-vagledning-2002-1.pdf): Vägledning 2002:1 Föräldrapenning: 12 kap. SFB |
| `tillfallig-foraldrapenning-vab` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e6/1782889809224/tillfallig-foraldrapenning-vagledning-2016-2.pdf): Vägledning 2016:2 Tillfällig föräldrapenning: 13 kap. SFB |
| `tio-dagar-efter-fodsel` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e6/1782889809224/tillfallig-foraldrapenning-vagledning-2016-2.pdf): Vägledning 2016:2 Tillfällig föräldrapenning, section 'i samband med barns födelse' (13 kap. SFB) |
| `graviditetspenning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbab0/1687779945886/graviditetspenning-vagledning-2002-6.pdf): Vägledning 2002:6 Graviditetspenning: 10 kap. SFB |
| `barnbidrag` | Försäkringskassan | `sfs-2010-110`, `sfs-1986-386` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbab1/1761132006229/barnbidrag-vagledning-2002-10.pdf): Vägledning 2002:10 Barnbidrag: 'Bidragen regleras i 15–16 kap. SFB'; Barnbidragsförordningen (1986:386) in its source list |
| `bostadsbidrag` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.3f8d59921814e0eaf805f6/1767337297742/bostadsbidrag-till-barnfamiljer-och-ungdomar-vagledning-2004-10.pdf): Vägledning 2004:10 Bostadsbidrag: 97–98 kap. SFB |
| `underhallsstod` | Försäkringskassan | `sfs-2010-110`, `sfs-1996-1036` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f31e/1792744622903/underhallsstod-vagledning-2001-9.pdf): Vägledning 2001:9 Underhållsstöd: 18–19 kap. SFB; Förordningen (1996:1036) om underhållsstöd |
| `adoptionsbidrag` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbab2/1661517619917/adoptionsbidrag-vagledning-2002-12.pdf): Vägledning 2002:12: 'Bestämmelserna om adoptionsbidrag finns i 21 kap. SFB' |
| `omvardnadsbidrag` | Försäkringskassan | `sfs-2010-110`, `sfs-2018-1614` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e2/1687421936364/omvardnadsbidrag-vagledning-2018-4.pdf): Vägledning 2018:4 Omvårdnadsbidrag: 22 kap. SFB; Förordningen (2018:1614) |
| `merkostnadsersattning` | Försäkringskassan | `sfs-2010-110`, `sfs-2018-1614` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e1/1715677531764/merkostnadsersattning-vagledning-2018-3.pdf): Vägledning 2018:3 Merkostnadsersättning: 50 kap. SFB; Förordningen (2018:1614) |
| `sjukpenning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.4facd080196508608b0d5/1789972339445/sjukpenning-rehabilitering-rehabiliteringsersattning-vagledning-2025-1.pdf): Vägledning 2025:1: 'Alla bestämmelser om beräkning av sjukpenning finns i 28 kap. SFB'; 27 kap. SFB |
| `narstaendepenning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbaac/1732708062035/narstaendepenning-vagledning-2003-3.pdf): Vägledning 2003:3: 'Bestämmelser om rätten till närståendepenning finns i 47 kap. SFB' |
| `arbetsskadeersattning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbaad/1749120200237/formaner-vid-arbetsskada-vagledning-2003-4.pdf): Vägledning 2003:4 Förmåner vid arbetsskada: 41 kap. SFB (livränta) and related chapters |
| `sjukersattning` | Försäkringskassan | `sfs-2010-110`, `sfs-2002-986` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e8/1780410874692/sjukersattning-vagledning-2013-1.pdf): Vägledning 2013:1 Sjukersättning: 35–37 kap. SFB; Förordningen (2002:986) |
| `aktivitetsersattning` | Försäkringskassan | `sfs-2010-110`, `sfs-2002-986` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6e9/1780410822825/aktivitetsersattning-vagledning-2013-2.pdf): Vägledning 2013:2: 'rätten till aktivitetsersättning enligt 33 kap. 5 § SFB'; Förordningen (2002:986) |
| `assistansersattning` | Försäkringskassan | `sfs-2010-110` | [basis](https://www.forsakringskassan.se/download/18.7b234aa517b3a0b7f372a5/1765877448325/assistansersattning-vagledning-2003-06.pdf): Vägledning 2003:6 Assistansersättning: 51 kap. SFB |
| `bilstod` | Försäkringskassan | `sfs-2010-110`, `sfs-2010-1745` | [basis](https://www.forsakringskassan.se/download/18.146767b11814e063bfbaab/1774249937204/bilstod-till-personer-med-funktionsnedsattning-vagledning-2003-1.pdf): Vägledning 2003:1: 'Bestämmelser om rätten till bilstöd finns i 52 kap. SFB' and Förordningen (2010:1745) |
| `bidrag-arbetshjalpmedel` | Försäkringskassan | `sfs-2010-110`, `sfs-1991-1046` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6f4/1719803443190/bidrag-till-arbetshjalpmedel-vagledning-2009-1.pdf): Vägledning 2009:1: 'Reglerna om bidrag till arbetshjälpmedel finns i 30 kap. 5 § socialförsäkringsbalken' and Förordningen (1991:1046) |
| `statligt-tandvardsstod` | Försäkringskassan | `sfs-2008-145`, `sfs-2008-193` | [basis](https://www.forsakringskassan.se/download/18.7fc616c01814e179a9f6f7/1790921181695/statligt-tandvardsstod-vagledning-2008-2.pdf): Vägledning 2008:2: 'Det statliga tandvårdsstödet regleras i ... lagen (2008:145) ... förordningen (2008:193)' |
| `jobbpremie` | Försäkringskassan | `sfs-2026-4` | [basis](https://www.forsakringskassan.se/download/18.6824ccfb19c0e5392cd162/1774512950518/statlig-jobbpremie-vagledning-2026-4.pdf): Vägledning 2026:4 Statlig jobbpremie: bestämmelserna i förordningen (2026:4) om statlig jobbpremie |
| `studiemedel` | Centrala studiestödsnämnden | `sfs-1999-1395`, `sfs-2000-655` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Studiestödslagen (1999:1395): 3 kap. studiemedel; Studiestödsförordningen (2000:655) per CSN's Förordningar page |
| `studiemedel-utlandsstudier` | Centrala studiestödsnämnden | `sfs-1999-1395`, `sfs-2000-655` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Studiestödslagen (1999:1395): 3 kap. studiemedel |
| `studiehjalp-gymnasiet` | Centrala studiestödsnämnden | `sfs-1999-1395`, `sfs-2000-655` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Studiestödslagen: 2 kap. studiehjälp (studiebidrag, inackorderingstillägg, extra tillägg) |
| `studiehjalp-extra-tillagg` | Centrala studiestödsnämnden | `sfs-1999-1395`, `sfs-2000-655` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Studiestödslagen: 2 kap. studiehjälp includes extra tillägg |
| `aterbetalning-studielan` | Centrala studiestödsnämnden | `sfs-1999-1395` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Studiestödslagen: 4 kap. återbetalning av studielån |
| `omstallningsstudiestod` | Centrala studiestödsnämnden | `sfs-2022-856`, `sfs-2022-857` | [basis](https://www.csn.se/om-csn/lag-och-ratt/lagar.html): Lag (2022:856) and Förordning (2022:857) om omställningsstudiestöd listed by CSN |
| `uppehallstillstand-arbete` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningslagen: villkor för att resa in, vistas och arbeta i Sverige; Utlänningsförordningen: uppehållstillstånd |
| `uppehallstillstand-familj` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningslagen and Utlänningsförordningen (uppehållstillstånd) |
| `uppehallstillstand-studier` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningslagen and Utlänningsförordningen (uppehållstillstånd) |
| `visering-besok` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningslagen: viseringsrätt; Utlänningsförordningen: visering |
| `permanent-uppehallstillstand` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningslagen and Utlänningsförordningen (uppehållstillstånd) |
| `asyl` | Migrationsverket | `sfs-2005-716`, `sfs-2026-999` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): utlänningslagen covers asyl; [page](https://www.migrationsverket.se/du-vill-ansoka/internationellt-skydd-asyl.html): the new mottagandelag replaced LMA on 1 October 2026 (Mottagandelag (2026:999)) |
| `framlingspass-resedokument` | Migrationsverket | `sfs-2005-716`, `sfs-2006-97` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Utlänningsförordningen: regler för resehandlingar |
| `svenskt-medborgarskap` | Migrationsverket | `sfs-2001-82`, `sfs-2001-218` | [basis](https://www.migrationsverket.se/om-migrationsverket/styrning-och-uppfoljning/lagar-och-forordningar.html): Lag (2001:82) reglerar förutsättningarna för ansökan om svenskt medborgarskap; Medborgarskapsförordning (2001:218) |
| `pass` | Polismyndigheten | `sfs-1978-302` | [basis](https://polisen.se/tjanster-tillstand/pass-och-nationellt-id-kort/svar-pa-vanliga-fragor-om-pass/): FAQ: skäl för avslag framgår av passlag (1978:302) 7 § |
| `nationellt-id-kort` | Polismyndigheten | `sfs-2005-661` | [basis](https://polisen.se/tjanster-tillstand/pass-och-nationellt-id-kort/svar-pa-vanliga-fragor-om-pass/): FAQ: skäl för avslag framgår av förordning (2005:661) om nationellt identitetskort |
| `provisoriskt-pass` | Polismyndigheten | `sfs-1978-302` | [basis](https://polisen.se/tjanster-tillstand/pass-och-nationellt-id-kort/svar-pa-vanliga-fragor-om-pass/): Passlag (1978:302) cited in Polisen's pass FAQ |
| `utdrag-belastningsregistret` | Polismyndigheten | `sfs-1998-620`, `sfs-1999-1134` | [page](https://polisen.se/tjanster-tillstand/belastningsregistret/kontrollera-dina-uppgifter-i-belastningsregistret/): Page cites lagen (1998:620) om belastningsregister and förordning (1999:1134) |
| `registerutdrag-skola-forskola` | Polismyndigheten | `sfs-1998-620`, `sfs-1999-1134`, `sfs-2010-800` | [page](https://polisen.se/tjanster-tillstand/belastningsregistret/skola-eller-forskola/): Page cites lagen (1998:620), förordning (1999:1134) and Skollag (2010:800) |
| `hittegods-forlustanmalan` | Polismyndigheten | `sfs-1938-121` | [page](https://polisen.se/tjanster-tillstand/hittegods/): Page links 'Lagen om hittegods' (1938:121) |
| `tillstand-offentlig-plats` | Polismyndigheten | `sfs-1993-1617` | [page](https://polisen.se/tjanster-tillstand/tillstand-ansok/offentlig-plats/): Page cites ordningslagen (1993:1617) |
| `tillstand-arrangemang` | Polismyndigheten | `sfs-1993-1617` | [page](https://polisen.se/tjanster-tillstand/tillstand-ansok/anordna-arrangemang/): Page cites ordningslagen (1993:1617) |
| `tillstand-fyrverkerier` | Polismyndigheten | `sfs-1993-1617` | [page](https://polisen.se/tjanster-tillstand/tillstand-ansok/fyrverkerier/): Page cites 3 kap. 7 § ordningslagen (1993:1617) |
| `tillstand-ordningsvakter` | Polismyndigheten | `sfs-2023-421` | [page](https://polisen.se/tjanster-tillstand/tillstand-ansok/anvanda-ordningsvakter/): Page cites lagen (2023:421) om ordningsvakter |
| `tillstand-begagnade-varor` | Polismyndigheten | `sfs-1999-271`, `sfs-1999-272` | [page](https://polisen.se/tjanster-tillstand/tillstand-ansok/begagnade-varor/): Page cites lagen (1999:271) och förordningen (1999:272) om handel med begagnade varor |
| `vapentillstand` | Polismyndigheten | `sfs-2026-408`, `sfs-2026-409` | [page](https://polisen.se/tjanster-tillstand/vapen-regler-och-tillstand/ansok-om-vapentillstand/): Page names vapenlagen and vapenförordningen; Polisen cites vapenlagen as (2026:408) on its begagnade-varor page; 2026:408/409 replaced 1996:67/70 on 2026-06-01 |
| `europeiskt-skjutvapenpass` | Polismyndigheten | `sfs-2026-408`, `sfs-2026-409` | [page](https://polisen.se/tjanster-tillstand/vapen-regler-och-tillstand/europeiskt-skjutvapenpass/): Page names vapenlagen and vapenförordningen (in force versions 2026:408/409) |
| `allman-handling-polisen` | Polismyndigheten | `sfs-1949-105`, `sfs-2009-400` | [page](https://polisen.se/tjanster-tillstand/ta-del-av-allman-handling/): Page names tryckfrihetsförordningen and offentlighets- och sekretesslagen |
| `korkortstillstand` | Transportstyrelsen | `sfs-1998-488`, `sfs-1998-980` | [basis](https://www.transportstyrelsen.se/sv/vagtrafik/korkort/regler-som-styr/): Transportstyrelsen 'Regler som styr' körkort: körkortslagen (1998:488), körkortsförordningen (1998:980) |
| `fornya-korkort` | Transportstyrelsen | `sfs-1998-488`, `sfs-1998-980` | [basis](https://www.transportstyrelsen.se/sv/vagtrafik/korkort/regler-som-styr/): Same 'Regler som styr' page |
| `ersattningskorkort` | Transportstyrelsen | `sfs-1998-488`, `sfs-1998-980` | [basis](https://www.transportstyrelsen.se/sv/vagtrafik/korkort/regler-som-styr/): Same 'Regler som styr' page |
| `nytt-korkort-efter-aterkallelse` | Transportstyrelsen | `sfs-1998-488`, `sfs-1998-980` | [basis](https://www.transportstyrelsen.se/sv/vagtrafik/korkort/regler-som-styr/): Same 'Regler som styr' page |
| `utlandskt-korkort` | Transportstyrelsen | `sfs-1998-488` | [page](https://www.transportstyrelsen.se/sv/vagtrafik/korkort/har-korkort/utlandska-korkort/): Page cites 3 § körkortslagen (1998:488) |
| `trangselskatt` | Transportstyrelsen | `sfs-2004-629` | [page](https://www.transportstyrelsen.se/sv/vagtrafik/fordon/skatter-och-avgifter/trangselskatt/): Page links Lag (2004:629) om trängselskatt |
| `byta-efternamn` | Skatteverket | `sfs-2016-1013` | [page](https://www.skatteverket.se/privat/folkbokforing/namn/bytaefternamn.4.76a43be412206334b89800020669.html): Page: efternamn 'enligt reglerna i lagen om personnamn' (2016:1013) |
| `kassaregister` | Skatteverket | `sfs-2011-1244` | [page](https://www.skatteverket.se/foretag/drivaforetag/kassaregister.4.121b82f011a74172e5880005263.html): Rättsinformation box: Skatteförfarandelagen |
| `personalliggare` | Skatteverket | `sfs-2011-1244` | [page](https://www.skatteverket.se/foretag/arbetsgivare/personalliggare.4.4f3d00a710cc9ae1c9c80007271.html): Rättsinformation box: Skatteförfarandelag |
| `varsel-permittering` | Arbetsförmedlingen | `sfs-1974-13` | [page](https://arbetsformedlingen.se/for-arbetsgivare/anmal-varsel-och-permittering): Page: 'skyldigheten att anmäla varsel regleras i främjandelagen (1974:13)' |

## Left out

Services considered for the seed whose basis could not be confirmed from the body's own pages, or that belong elsewhere:

| service | issuer | reason |
| --- | --- | --- |
| Flyttanmälan | Skatteverket | No legal reference on the page or its subpages; the "Rättsinformation" links go to Rättslig vägledning on `www4.skatteverket.se`, which is WAF-blocked. Annex II procedure, so worth adding once the basis is confirmed. |
| Personbevis | Skatteverket | No legal reference on the page. |
| Skatteverkets id-kort | Skatteverket | The page cites only EU regulations on other countries' id cards, not the Swedish basis. |
| Byta förnamn, namn för nyfött barn | Skatteverket | The "Rättsinformation" box names only Rättslig vägledning topics ("Förnamn"), not an act; byta efternamn is in the seed because its page names lagen om personnamn. |
| Hindersprövning, bouppteckning, skilsmässa | Skatteverket | No act named on the pages; bouppteckning links only the Rättslig vägledning topic. |
| F-skatt, momsregistrering, arbetsgivarregistrering, momsdeklaration | Skatteverket | No act named; the moms page names only the Rättslig vägledning topic "Mervärdesskatt". Business core services, so worth adding once the basis is confirmed. |
| Starta och registrera företag (all verksamt.se pages) | Bolagsverket, Skatteverket, Tillväxtverket | verksamt.se renders its content with JavaScript, so neither the lead nor any legal reference is in the HTML; bolagsverket.se answers with a bot check (recorded for BOLFS). |
| Skriv in dig som arbetssökande, arbetsmarknadsutbildning | Arbetsförmedlingen | The pages name no act; Arbetsförmedlingen's governance page lists förordningarna 2000:628 and 2000:634 only as its general remit, without tying them to a service. |
| Nystartsjobb | Arbetsförmedlingen | The page names socialavgiftslagen and other acts for side conditions, not the act the support rests on. |
| Ägarbyte, avställning, avregistrering, fordonsskatt | Transportstyrelsen | No act named on the pages; the registreringsskyltar page cites only förordningen (2001:650) om vägtrafikregister. |
| Återvandringsbidrag | Migrationsverket | Migrationsverket's law list cites förordning (1984:890), repealed 2026-01-01; the corpus has Förordning (2025:970) om återvandringsbidrag för vissa utlänningar, but the agency does not name it, so it needs the owner's check before it is listed. |
| Skydd enligt massflyktsdirektivet | Migrationsverket | The agency cites the EU directive and its implementing decision, not the Swedish provisions. |
| Körkortslån, hemutrustningslån | Centrala studiestödsnämnden | The ordinances are named by CSN (2018:1118, 1990:1361), but no application page for either was found in CSN's sitemap, only repayment pages. |
| Bostadstillägg | Försäkringskassan / Pensionsmyndigheten | Not checked against a vägledning in this spike. |
| Healthcare services on 1177.se | the regions | Regional services; they belong to the region template services, not to the national seed. |
