"""Closed vocabularies for the corpus: layers and document types."""

LAYERS = (
    "fundamental",
    "sfs",
    "agency",
    "case_law",
    "eu",
    "region",
    "municipality",
    "service",
)

# type -> layer, in the order the API lists a layer's series
TYPES = {
    "fundamental_law": "fundamental",
    "act": "sfs",
    "ordinance": "sfs",
    "other_statute": "sfs",
    "agency_regulation": "agency",
    "case_report": "case_law",
    "case_notice": "case_law",
    "eu_regulation": "eu",
    "eu_directive": "eu",
    "eu_decision": "eu",
    "county_regulation": "region",
    "municipal_regulation": "municipality",
}

# Types whose numbers and references are SFS numbers.
SFS_TYPES = ("fundamental_law", "act", "ordinance", "other_statute")
