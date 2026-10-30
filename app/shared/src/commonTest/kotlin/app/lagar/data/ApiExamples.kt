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
  ],
  "docs_encoding": "json"
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
    {"id": "sfs-2010-800", "title": "Skollag (2010:800)", "number": "2010:800", "type": "act", "issued": "2010-06-23", "repealed": null, "in_force": "2011-07-01", "amended_through": "2026:1636", "ministry": "Utbildningsdepartementet", "region_code": null, "municipality_code": null},
    {"id": "sfs-1999-175", "title": "Rättsinformationsförordning (1999:175)", "number": "1999:175", "type": "ordinance", "issued": "1999-03-25", "repealed": null, "in_force": null, "amended_through": "2026:851", "ministry": "Justitiedepartementet KRIM", "region_code": null, "municipality_code": null},
    {"id": "sfs-1999-100", "title": "Exempelförordning (1999:100)", "number": "1999:100", "type": "ordinance", "issued": "1999-03-25", "repealed": "2005-01-01", "in_force": "1999-07-01", "amended_through": null, "ministry": null, "region_code": null, "municipality_code": null}
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
    {"id": "sfs-2010-800", "title": "Skollag (2010:800)", "number": "2010:800", "type": "act", "issued": "2010-06-23", "repealed": null, "in_force": "2011-07-01", "amended_through": "2026:1636", "ministry": "Utbildningsdepartementet", "region_code": null, "municipality_code": null}
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
    "fetched_at": "2026-10-27T10:00:00Z",
    "amendments": null
  },
  "body": "# Rättsinformationsförordning (1999:175)\n\nEtt offentligt rättsinformationssystem\n\n**1 §** I syfte att tillförsäkra den offentliga förvaltningen och enskilda tillgång till grundläggande rättsinformation i elektronisk form skall det finnas ett offentligt rättsinformationssystem.\n"
}
"""

    /** The document example as built before `amendments` existed: the key is absent. */
    val legacyDocument = """
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

    val ordinanceMinistries = """
{
  "layer": "sfs",
  "type": "ordinance",
  "total": 2,
  "unassigned": 1,
  "ministries": [
    {"id": "justitiedepartementet", "name": "Justitiedepartementet", "count": 1}
  ]
}
"""

    val ordinanceMinistryListing = """
{
  "layer": "sfs",
  "type": "ordinance",
  "ministry_id": "justitiedepartementet",
  "ministry": "Justitiedepartementet",
  "page": 1,
  "page_count": 1,
  "total": 1,
  "items": [
    {"id": "sfs-1999-175", "title": "Rättsinformationsförordning (1999:175)", "number": "1999:175", "type": "ordinance", "issued": "1999-03-25", "repealed": null, "in_force": null, "amended_through": "2026:851", "ministry": "Justitiedepartementet KRIM", "region_code": null, "municipality_code": null}
  ]
}
"""

    /** A document whose `amendments` were read from the SFS register. */
    val documentWithAmendments = """
{
  "meta": {
    "id": "sfs-1974-152",
    "title": "Regeringsformen",
    "type": "fundamental_law",
    "layer": "fundamental",
    "number": "1974:152",
    "issued": "1974-02-28",
    "in_force": "1975-01-01",
    "repealed": null,
    "amended_by": ["1976:871", "2022:1600"],
    "amended_through": "2022:1600",
    "reprinted_by": ["2011:109"],
    "ministry": "Justitiedepartementet L6",
    "eli": null,
    "language": "sv",
    "authoritative": false,
    "source": "https://data.riksdagen.se/dokument/sfs-1974-152",
    "source_sha256": "dc5c705c609a888f25b7beb2b0658980fbfe0a3bfccc43a16cd991377942699a",
    "fetched_at": "2026-10-27T13:17:26Z",
    "amendments": [
      {
        "number": "1976:871",
        "title": "Lag (1976:871) om ändring i regeringsformen",
        "scope": "ändr. 1 kap 9 §",
        "preparatory_works": "Prop. 1975/76:209",
        "celex": null,
        "in_force": null,
        "in_force_raw": null
      },
      {
        "number": "2022:1600",
        "title": null,
        "scope": null,
        "preparatory_works": null,
        "celex": null,
        "in_force": "2023-01-01",
        "in_force_raw": "2023-01-01 överg.best."
      }
    ]
  },
  "body": "# Regeringsformen\n"
}
"""

    val regionCodes = """
{
  "layer": "region",
  "field": "region_code",
  "total": 1,
  "codes": [
    {"code": "01", "count": 1}
  ]
}
"""

    val regionCodeListing = """
{
  "layer": "region",
  "type": null,
  "code": "01",
  "page": 1,
  "page_count": 1,
  "total": 1,
  "items": [
    {"id": "01fs-2024-3", "title": "Föreskrifter om naturreservatet Exempelskogen", "number": "01FS 2024:3", "type": "county_regulation", "issued": "2024-02-01", "repealed": null, "in_force": "2024-03-01", "amended_through": null, "ministry": null, "region_code": "01", "municipality_code": null}
  ]
}
"""

    val municipalityCodeListing = """
{
  "layer": "municipality",
  "type": null,
  "code": "0180",
  "page": 1,
  "page_count": 1,
  "total": 1,
  "items": [
    {"id": "0180-2024-12", "title": "Lokala ordningsföreskrifter för Stockholms kommun", "number": "SKFS 2024:12", "type": "municipal_regulation", "issued": "2024-05-06", "repealed": null, "in_force": null, "amended_through": null, "ministry": null, "region_code": "01", "municipality_code": "0180"}
  ]
}
"""
}
