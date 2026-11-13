"""Closed vocabularies for the corpus: layers, document types and public-service fields."""

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
    "treaty": "sfs",
    "agency_regulation": "agency",
    "case_report": "case_law",
    "case_notice": "case_law",
    "eu_regulation": "eu",
    "eu_directive": "eu",
    "eu_decision": "eu",
    "eu_judgment": "eu",
    "county_regulation": "region",
    "municipal_regulation": "municipality",
    "public_service": "service",
}

# Types whose numbers and references are SFS numbers.
SFS_TYPES = ("fundamental_law", "act", "ordinance", "other_statute")

# public_service fields (docs/specs/2026-11-13-tjanster-design.md, "Corpus").
SERVICE_AUDIENCES = ("private", "business")
SERVICE_TOPICS = (
    "family",
    "work",
    "business",
    "housing",
    "health",
    "tax",
    "vehicles",
    "education",
    "migration",
    "social_support",
    "environment",
    "legal",
)
SERVICE_CHANNELS = ("online", "form", "phone", "office")
SERVICE_SCOPES = ("national", "region", "municipality")
