# Progress

Volume does not prove completeness: a series at 100% of its target only means every counted document is present, and a high count says nothing about gaps in coverage, missing amendments or text quality. See [COVERAGE.md](COVERAGE.md).

![Progress per series](progress.svg)

| layer | series | collected | target | kind | % |
| --- | --- | ---: | ---: | --- | ---: |
| fundamental | Fundamental laws | 4 | 4 | counted | 100.0% |
| sfs | SFS (statutes and ordinances) | 11428 | 11567 | counted | 98.8% |
| agency | AFS (Arbetsmiljöverket) | 15 | 15 | counted | 100.0% |
| agency | FFFS (Finansinspektionen) | 121 | 121 | counted | 100.0% |
| agency | TSFS (Transportstyrelsen) | 622 | 622 | counted | 100.0% |
| case_law | Case law | 16390 | 16640 | counted | 98.5% |
| eu | EU law (curated list) | 70 | 70 | curated | 100.0% |
| region | Regional regulations | 630 | 630 | counted | 100.0% |
| municipality | Municipal regulations | 15 | unknown | unknown | - |
| service | Public services | 0 | unknown | unknown | - |

Progress is capped at the target; a series without a known target has no percentage.

SFS (statutes and ordinances) breakdown: 3000 acts, 6591 ordinances, 1837 other statutes.

Targets:
- Fundamental laws: counted, The four Swedish fundamental laws, as of 2026-10-27
- SFS (statutes and ordinances): counted, https://data.riksdagen.se/dokumentlista/?doktyp=sfs, as of 2026-10-27
- AFS (Arbetsmiljöverket): counted, https://www.av.se/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/ (Gällande grundföreskrifter), as of 2026-10-29
- FFFS (Finansinspektionen): counted, https://www.fi.se/sv/vara-register/fffs/forteckning-fffs/ (base regulations in force), as of 2026-10-29
- TSFS (Transportstyrelsen): counted, https://www.transportstyrelsen.se/sv/om-oss/dina-rattigheter-lagar-och-regler/forfattningssamling/ts-foreskrifter-i-nummerordning/ (base regulations on the year listings, 331 in force and 291 repealed), as of 2026-10-29
- Case law: counted, https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar?publiceringsformer=referat,notis, as of 2026-10-29
- EU law (curated list): curated, collector/data/eu-acts.json, as of 2026-10-29
- Regional regulations: counted, https://www.lansstyrelsen.se (numbered regulations on the 21 county landing pages in collector/data/counties.json, 2025–2026), as of 2026-10-29

## Integrity

Audit of 29295 documents (2026-10-29T13:56:15Z):

- schema errors: 0
- duplicate ids: 0
- path mismatches: 0
- text-quality flags: 714
- cross-references not in the corpus: 38283 of 38341 (informational, the corpus is partial)
