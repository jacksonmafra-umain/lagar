# Progress

Volume does not prove completeness: a series at 100% of its target only means every counted document is present, and a high count says nothing about gaps in coverage, missing amendments or text quality. See [COVERAGE.md](COVERAGE.md).

![Progress per series](progress.svg)

| layer | series | collected | target | kind | % |
| --- | --- | ---: | ---: | --- | ---: |
| fundamental | Fundamental laws | 4 | 4 | counted | 100.0% |
| sfs | SFS (statutes and ordinances) | 100 | 11567 | counted | 0.9% |
| agency | Agency regulations | 0 | unknown | unknown | - |
| case_law | Case law | 0 | unknown | unknown | - |
| eu | EU law | 0 | unknown | unknown | - |
| region | Regional regulations | 0 | unknown | unknown | - |
| municipality | Municipal regulations | 0 | unknown | unknown | - |
| service | Public services | 0 | unknown | unknown | - |

Progress is capped at the target; a series without a known target has no percentage.

SFS (statutes and ordinances) breakdown: 48 acts, 50 ordinances, 2 other statutes.

Targets:
- Fundamental laws: counted, The four Swedish fundamental laws, as of 2026-10-27
- SFS (statutes and ordinances): counted, https://data.riksdagen.se/dokumentlista/?doktyp=sfs, as of 2026-10-27

## Integrity

Audit of 104 documents (2026-10-28T00:00:00Z):

- schema errors: 0
- duplicate ids: 0
- path mismatches: 0
- text-quality flags: 7
- cross-references not in the corpus: 80 of 81 (informational, the corpus is partial)
