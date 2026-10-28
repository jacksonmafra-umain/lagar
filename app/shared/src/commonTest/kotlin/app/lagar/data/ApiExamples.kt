package app.lagar.data

/** Verbatim copies of the canonical contract examples in docs/api/examples. */
object ApiExamples {
    val index = """
{
  "api_version": 1,
  "built_at": "2026-10-27T10:30:00Z",
  "layers": [
    {"id": "fundamental", "count": 0, "series": []},
    {"id": "sfs", "count": 3, "series": [{"id": "act", "count": 1}, {"id": "ordinance", "count": 2}]},
    {"id": "agency", "count": 0, "series": []},
    {"id": "case_law", "count": 0, "series": []},
    {"id": "eu", "count": 0, "series": []},
    {"id": "region", "count": 0, "series": []},
    {"id": "municipality", "count": 0, "series": []},
    {"id": "service", "count": 0, "series": []}
  ]
}
"""

    val sfsListing = """
{
  "layer": "sfs",
  "type": null,
  "page": 1,
  "page_count": 1,
  "total": 3,
  "items": [
    {"id": "sfs-2010-800", "title": "Skollag (2010:800)", "number": "2010:800", "type": "act", "issued": "2010-06-23", "repealed": null, "in_force": "2011-07-01", "amended_through": "2026:1636", "ministry": "Utbildningsdepartementet"},
    {"id": "sfs-1999-175", "title": "Rättsinformationsförordning (1999:175)", "number": "1999:175", "type": "ordinance", "issued": "1999-03-25", "repealed": null, "in_force": null, "amended_through": "2026:851", "ministry": "Justitiedepartementet KRIM"},
    {"id": "sfs-1999-100", "title": "Exempelförordning (1999:100)", "number": "1999:100", "type": "ordinance", "issued": "1999-03-25", "repealed": "2005-01-01", "in_force": "1999-07-01", "amended_through": null, "ministry": null}
  ]
}
"""

    val actListing = """
{
  "layer": "sfs",
  "type": "act",
  "page": 1,
  "page_count": 1,
  "total": 1,
  "items": [
    {"id": "sfs-2010-800", "title": "Skollag (2010:800)", "number": "2010:800", "type": "act", "issued": "2010-06-23", "repealed": null, "in_force": "2011-07-01", "amended_through": "2026:1636", "ministry": "Utbildningsdepartementet"}
  ]
}
"""

    /** A listing as served before `in_force`, `amended_through` and `ministry` were added to items. */
    val legacyListing = """
{
  "layer": "sfs",
  "type": "act",
  "page": 1,
  "page_count": 1,
  "total": 1,
  "items": [
    {"id": "sfs-2010-800", "title": "Skollag (2010:800)", "number": "2010:800", "type": "act", "issued": "2010-06-23", "repealed": null}
  ]
}
"""

    val document = """
{
  "meta": {
    "id": "sfs-1999-175",
    "title": "Rättsinformationsförordning (1999:175)",
    "type": "ordinance",
    "layer": "sfs",
    "number": "1999:175",
    "issued": "1999-03-25",
    "in_force": null,
    "repealed": null,
    "amended_by": [],
    "amended_through": "2026:851",
    "reprinted_by": [],
    "ministry": "Justitiedepartementet KRIM",
    "eli": null,
    "language": "sv",
    "authoritative": false,
    "source": "https://data.riksdagen.se/dokument/sfs-1999-175",
    "source_sha256": "9f2b6c1d4e8a7035b1c6d2e9f4a83b70c5d1e6f2a9b84c3d7e0f1a2b3c4d5e6f",
    "fetched_at": "2026-10-27T10:00:00Z"
  },
  "body": "# Rättsinformationsförordning (1999:175)\n\nEtt offentligt rättsinformationssystem\n\n**1 §** I syfte att tillförsäkra den offentliga förvaltningen och enskilda tillgång till grundläggande rättsinformation i elektronisk form skall det finnas ett offentligt rättsinformationssystem.\n"
}
"""
}
