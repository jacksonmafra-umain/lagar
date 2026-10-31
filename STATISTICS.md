# Corpus statistics

Generated 2026-10-31T23:41:28Z by `collector/stats.py` from the corpus, the source manifests and the audit report. Every number is computed from files in this repository.

## Documents

The corpus holds 54,786 documents in 7 layers.

| layer | type | documents | sections (§) | words |
| --- | --- | ---: | ---: | ---: |
| fundamental | fundamental_law | 4 | 494 | 33,286 |
| sfs | act | 3,000 | 93,738 | 8,804,639 |
| sfs | ordinance | 6,591 | 101,864 | 6,895,220 |
| sfs | other_statute | 1,837 | 12,462 | 1,343,279 |
| sfs | treaty | 3,515 | 75 | 2,002,459 |
| agency | agency_regulation | 5,468 | 61,190 | 14,296,515 |
| case_law | case_report | 16,404 | 715 | 55,713,491 |
| case_law | case_notice | 71 | 4 | 93,635 |
| eu | eu_regulation | 40 | 0 | 2,191,225 |
| eu | eu_directive | 28 | 0 | 651,177 |
| eu | eu_decision | 2 | 0 | 14,266 |
| eu | eu_judgment | 605 | 35 | 3,651,042 |
| region | county_regulation | 11,649 | 14,166 | 10,999,529 |
| municipality | municipal_regulation | 5,572 | 44,907 | 12,425,695 |

Sections count paragraphs that open with a section number (`1 §`, `2 a §`); case law and EU documents have none.

## Issuers and places

| layer | distinct issuers |
| --- | ---: |
| agency | 77 |
| case_law | 20 |
| eu | 5 |
| fundamental | 1 |
| municipality | 285 |
| region | 21 |
| sfs | 208 |

County regulations cover 21 of 21 counties; municipal regulations cover 285 of 290 kommuner.

## Origins

Documents per host of their `source`, per layer (the ten largest).

### fundamental

| host | documents |
| --- | ---: |
| data.riksdagen.se | 4 |

### sfs

| host | documents |
| --- | ---: |
| data.riksdagen.se | 11,428 |
| regeringen.se | 3,515 |

### agency

| host | documents |
| --- | ---: |
| foreskrifter.riksarkivet.se | 1,363 |
| skolfs.skolverket.se | 965 |
| transportstyrelsen.se | 708 |
| lagrummet.forsakringskassan.se | 368 |
| regelverk.swedac.se | 187 |
| naturvardsverket.se | 164 |
| domstol.se | 154 |
| fi.se | 121 |
| socialstyrelsen.se | 121 |
| pensionsmyndigheten.se | 81 |
| 55 other hosts | 1,236 |

### case_law

| host | documents |
| --- | ---: |
| rattspraxis.etjanst.domstol.se | 16,475 |

### eu

| host | documents |
| --- | ---: |
| publications.europa.eu | 675 |

### region

| host | documents |
| --- | ---: |
| lansstyrelsen.se | 11,649 |

### municipality

| host | documents |
| --- | ---: |
| docs.netpublicator.com | 104 |
| gallivare.se | 60 |
| karlshamn.se | 58 |
| pitea.se | 57 |
| boras.se | 56 |
| uddevalla.se | 54 |
| lerum.se | 51 |
| laholm.se | 49 |
| ale.se | 49 |
| lillaedet.se | 49 |
| 275 other hosts | 4,985 |

## How the text was obtained

| layer | web page or API | PDF text layer | OCR of a scan | no text (metadata and link) |
| --- | ---: | ---: | ---: | ---: |
| fundamental | 4 | 0 | 0 | 0 |
| sfs | 14,391 | 257 | 35 | 260 |
| agency | 291 | 4,426 | 740 | 11 |
| case_law | 16,475 | 0 | 0 | 0 |
| eu | 675 | 0 | 0 | 0 |
| region | 420 | 10,768 | 428 | 33 |
| municipality | 197 | 4,922 | 284 | 169 |
| **all** | **32,453** (59.2 %) | **20,373** (37.2 %) | **1,487** (2.7 %) | **473** (0.9 %) |

OCR text is marked `text_source: ocr` in the frontmatter and may contain misread characters; the PDF stays the authoritative source.

## PDFs and OCR

Issuers whose documents rely on a PDF (the text comes from it, or only a PDF is linked), and how many of those PDFs are scans without a readable text layer.

| layer | issuers using PDF | documents | issuers with scans | scanned | read by OCR | still without text |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| agency | 75 | 5,391 | 12 | 743 | 740 | 3 |
| municipality | 280 | 5,469 | 144 | 346 | 284 | 62 |
| region | 21 | 11,589 | 15 | 461 | 428 | 33 |
| sfs | 3 | 293 | 1 | 36 | 35 | 1 |

### Issuers with scanned PDFs

| issuer | documents | scanned | read by OCR |
| --- | ---: | ---: | ---: |
| agency: Centrala studiestödsnämnden | 63 | 4 | 4 |
| agency: Försvarsmakten | 61 | 1 | 1 |
| agency: Konsumentverket | 22 | 1 | 1 |
| agency: Lantmäteriet | 20 | 2 | 1 |
| agency: Naturvårdsverket | 164 | 9 | 9 |
| agency: Polismyndigheten | 79 | 3 | 3 |
| agency: Riksarkivet | 1,363 | 707 | 705 |
| agency: Sametinget | 13 | 1 | 1 |
| agency: Sjöfartsverket | 44 | 7 | 7 |
| agency: Socialstyrelsen | 110 | 4 | 4 |
| agency: Statens energimyndighet | 65 | 3 | 3 |
| agency: Transportstyrelsen | 622 | 1 | 1 |
| municipality: Ale kommun | 49 | 10 | 5 |
| municipality: Alingsås kommun | 36 | 1 | 1 |
| municipality: Arjeplogs kommun | 47 | 8 | 7 |
| municipality: Askersunds kommun | 18 | 6 | 6 |
| municipality: Avesta kommun | 4 | 1 | 1 |
| municipality: Bergs kommun | 26 | 2 | 1 |
| municipality: Bodens kommun | 10 | 6 | 3 |
| municipality: Bollnäs kommun | 7 | 1 | 1 |
| municipality: Boxholms kommun | 16 | 1 | 1 |
| municipality: Bromölla kommun | 38 | 1 | 0 |
| municipality: Dals-Eds kommun | 5 | 1 | 1 |
| municipality: Danderyds kommun | 22 | 1 | 1 |
| municipality: Dorotea kommun | 14 | 1 | 1 |
| municipality: Eda kommun | 26 | 1 | 0 |
| municipality: Ekerö kommun | 34 | 7 | 2 |
| municipality: Eskilstuna kommun | 20 | 1 | 1 |
| municipality: Eslövs kommun | 32 | 3 | 0 |
| municipality: Essunga kommun | 29 | 4 | 3 |
| municipality: Fagersta kommun | 23 | 1 | 1 |
| municipality: Falköpings kommun | 30 | 2 | 2 |
| municipality: Falu kommun | 15 | 1 | 1 |
| municipality: Forshaga kommun | 12 | 3 | 3 |
| municipality: Gagnefs kommun | 4 | 1 | 1 |
| municipality: Gnesta kommun | 19 | 2 | 2 |
| municipality: Gullspångs kommun | 31 | 1 | 1 |
| municipality: Gällivare kommun | 60 | 3 | 3 |
| municipality: Göteborgs Stad | 43 | 1 | 1 |
| municipality: Habo kommun | 6 | 1 | 1 |
| municipality: Hallsbergs kommun | 31 | 7 | 2 |
| municipality: Hallstahammars kommun | 32 | 6 | 6 |
| municipality: Halmstads kommun | 8 | 1 | 0 |
| municipality: Haninge kommun | 16 | 2 | 2 |
| municipality: Haparanda stad | 18 | 1 | 1 |
| municipality: Heby kommun | 23 | 1 | 1 |
| municipality: Hedemora kommun | 29 | 2 | 2 |
| municipality: Helsingborgs stad | 10 | 1 | 1 |
| municipality: Herrljunga kommun | 13 | 1 | 1 |
| municipality: Huddinge kommun | 36 | 1 | 1 |
| municipality: Hällefors kommun | 9 | 1 | 1 |
| municipality: Härnösands kommun | 14 | 1 | 1 |
| municipality: Håbo kommun | 27 | 4 | 4 |
| municipality: Hörby kommun | 6 | 1 | 1 |
| municipality: Jokkmokks kommun | 30 | 6 | 6 |
| municipality: Järfälla kommun | 16 | 8 | 5 |
| municipality: Kalix kommun | 25 | 1 | 1 |
| municipality: Kalmar kommun | 39 | 2 | 2 |
| municipality: Katrineholms kommun | 36 | 1 | 1 |
| municipality: Kinda kommun | 14 | 3 | 3 |
| municipality: Klippans kommun | 16 | 1 | 0 |
| municipality: Kramfors kommun | 27 | 5 | 5 |
| municipality: Kristianstads kommun | 27 | 2 | 2 |
| municipality: Kristinehamns kommun | 19 | 4 | 2 |
| municipality: Kungälvs kommun | 37 | 3 | 3 |
| municipality: Kävlinge kommun | 23 | 3 | 3 |
| municipality: Köpings kommun | 7 | 1 | 1 |
| municipality: Laholms kommun | 49 | 8 | 3 |
| municipality: Landskrona stad | 29 | 3 | 3 |
| municipality: Laxå kommun | 6 | 1 | 1 |
| municipality: Leksands kommun | 20 | 1 | 1 |
| municipality: Lerums kommun | 51 | 9 | 5 |
| municipality: Lessebo kommun | 9 | 3 | 3 |
| municipality: Lidingö stad | 18 | 1 | 0 |
| municipality: Lindesbergs kommun | 8 | 1 | 1 |
| municipality: Ljungby kommun | 14 | 1 | 1 |
| municipality: Ljusdals kommun | 21 | 1 | 1 |
| municipality: Ljusnarsbergs kommun | 9 | 1 | 1 |
| municipality: Lomma kommun | 50 | 1 | 1 |
| municipality: Ludvika kommun | 19 | 4 | 4 |
| municipality: Luleå kommun | 12 | 3 | 2 |
| municipality: Lysekils kommun | 15 | 1 | 1 |
| municipality: Malung-Sälens kommun | 4 | 1 | 1 |
| municipality: Mariestads kommun | 24 | 1 | 1 |
| municipality: Markaryds kommun | 12 | 1 | 1 |
| municipality: Marks kommun | 25 | 1 | 1 |
| municipality: Mjölby kommun | 5 | 1 | 0 |
| municipality: Mora kommun | 28 | 2 | 2 |
| municipality: Motala kommun | 32 | 1 | 1 |
| municipality: Munkfors kommun | 5 | 2 | 2 |
| municipality: Mölndals stad | 23 | 3 | 3 |
| municipality: Nacka kommun | 19 | 1 | 1 |
| municipality: Norbergs kommun | 16 | 3 | 3 |
| municipality: Nordanstigs kommun | 8 | 1 | 1 |
| municipality: Norsjö kommun | 14 | 2 | 1 |
| municipality: Nykvarns kommun | 15 | 1 | 0 |
| municipality: Nyköpings kommun | 33 | 1 | 1 |
| municipality: Nynäshamns kommun | 39 | 3 | 3 |
| municipality: Osby kommun | 5 | 1 | 1 |
| municipality: Ovanåkers kommun | 6 | 3 | 3 |
| municipality: Piteå kommun | 57 | 1 | 1 |
| municipality: Rättviks kommun | 26 | 2 | 1 |
| municipality: Sala kommun | 30 | 1 | 1 |
| municipality: Salems kommun | 11 | 1 | 1 |
| municipality: Sjöbo kommun | 6 | 1 | 1 |
| municipality: Skövde kommun | 15 | 4 | 4 |
| municipality: Smedjebacken kommun | 35 | 2 | 2 |
| municipality: Sorsele kommun | 30 | 4 | 4 |
| municipality: Sotenäs kommun | 19 | 2 | 2 |
| municipality: Storfors kommun | 7 | 6 | 6 |
| municipality: Strängnäs kommun | 31 | 2 | 2 |
| municipality: Strömstads kommun | 28 | 4 | 4 |
| municipality: Strömsunds kommun | 9 | 1 | 0 |
| municipality: Sundsvalls kommun | 18 | 4 | 4 |
| municipality: Surahammars kommun | 34 | 2 | 2 |
| municipality: Svalöv kommun | 27 | 13 | 13 |
| municipality: Svenljunga kommun | 28 | 2 | 2 |
| municipality: Säffle kommun | 20 | 2 | 2 |
| municipality: Söderhamns kommun | 33 | 4 | 4 |
| municipality: Söderköpings kommun | 9 | 1 | 1 |
| municipality: Södertälje kommun | 10 | 1 | 0 |
| municipality: Sölvesborg kommun | 29 | 1 | 1 |
| municipality: Timrå kommun | 38 | 4 | 4 |
| municipality: Tingsryds kommun | 10 | 3 | 3 |
| municipality: Tjörns kommun | 15 | 1 | 1 |
| municipality: Tomelilla kommun | 25 | 1 | 1 |
| municipality: Torsås kommun | 4 | 1 | 1 |
| municipality: Trollhättans stad | 28 | 10 | 7 |
| municipality: Tyresö kommun | 9 | 1 | 0 |
| municipality: Töreboda kommun | 15 | 1 | 1 |
| municipality: Ulricehamns kommun | 11 | 1 | 0 |
| municipality: Upplands Väsby kommun | 29 | 1 | 1 |
| municipality: Vaggeryds kommun | 12 | 1 | 1 |
| municipality: Valdemarsviks kommun | 21 | 4 | 2 |
| municipality: Varbergs kommun | 29 | 2 | 1 |
| municipality: Vaxholms stad | 4 | 1 | 1 |
| municipality: Vilhelmina kommun | 22 | 1 | 1 |
| municipality: Vänersborgs kommun | 37 | 1 | 1 |
| municipality: Värmdö kommun | 25 | 4 | 2 |
| municipality: Västerås stad | 21 | 2 | 1 |
| municipality: Vårgårda kommun | 20 | 4 | 4 |
| municipality: Ydre kommun | 12 | 2 | 2 |
| municipality: Ystads kommun | 14 | 1 | 1 |
| municipality: Älmhults kommun | 6 | 2 | 2 |
| municipality: Älvdalens kommun | 9 | 1 | 1 |
| municipality: Ånge kommun | 9 | 2 | 2 |
| municipality: Åre kommun | 30 | 3 | 3 |
| municipality: Årjängs kommun | 21 | 4 | 4 |
| municipality: Åstorps kommun | 26 | 2 | 2 |
| municipality: Ödeshögs kommun | 14 | 1 | 1 |
| municipality: Örebro kommun | 33 | 2 | 2 |
| municipality: Örkelljunga kommun | 10 | 1 | 1 |
| municipality: Örnsköldsviks kommun | 9 | 1 | 0 |
| municipality: Östhammars kommun | 22 | 3 | 3 |
| municipality: Överkalix kommun | 15 | 5 | 5 |
| municipality: Övertorneå kommun | 17 | 1 | 1 |
| region: Länsstyrelsen i Blekinge län | 981 | 123 | 112 |
| region: Länsstyrelsen i Dalarnas län | 571 | 23 | 22 |
| region: Länsstyrelsen i Gotlands län | 91 | 1 | 1 |
| region: Länsstyrelsen i Jämtlands län | 1,648 | 25 | 19 |
| region: Länsstyrelsen i Kalmar län | 1,412 | 85 | 81 |
| region: Länsstyrelsen i Kronobergs län | 360 | 81 | 80 |
| region: Länsstyrelsen i Norrbottens län | 736 | 2 | 2 |
| region: Länsstyrelsen i Södermanlands län | 365 | 44 | 44 |
| region: Länsstyrelsen i Uppsala län | 388 | 8 | 8 |
| region: Länsstyrelsen i Västerbottens län | 161 | 2 | 2 |
| region: Länsstyrelsen i Västernorrlands län | 548 | 14 | 14 |
| region: Länsstyrelsen i Västmanlands län | 164 | 5 | 5 |
| region: Länsstyrelsen i Västra Götalands län | 264 | 11 | 8 |
| region: Länsstyrelsen i Örebro län | 1,800 | 19 | 18 |
| region: Länsstyrelsen i Östergötlands län | 286 | 18 | 12 |
| sfs: Utrikesdepartementet | 286 | 36 | 35 |

## Quality and accuracy

### Corpus audit

- Documents checked: 54,786
- Schema errors: 0; duplicate ids: 0; path mismatches: 0
- Text-quality flags: print_only 259, replacement_character 97, short_body 548
- Amendment references (`amended_by`, `amended_through`, `reprinted_by`) to documents not in the corpus: 39,935 of 39,996 (mostly older amending acts, which are not collected as documents of their own)

### SFS text against the official PDF

Riksdagen's text of each statute is compared word by word with the printed SFS PDF (`sources/sfs-pdf-verification.json`).

- Statuses: amended 513, differs 47, match 635, no_corpus_document 12,240, print_only 8, repealed 104
- Of 682 statutes printed in their current wording, 93.1 % match the print (word coverage at least 0.97).

### OCR accuracy

Measured on 47 official PDFs that have a text layer, read a second time by OCR and compared with the text layer (`sources/ocr-calibration.json`, 2026-10-31T17:37:02Z). Pages rendered from a text layer are cleaner than paper scans, so these numbers are an upper bound for the scanned PDFs read by OCR.

| measure | mean | median | lowest |
| --- | ---: | ---: | ---: |
| word recall (text-layer words OCR found) | 95.5 % | 95.9 % | 90.8 % |
| word precision (OCR words in the text layer) | 94.2 % | 94.6 % | 74.4 % |
| character similarity | 91.8 % | 97.0 % | 63.8 % |

