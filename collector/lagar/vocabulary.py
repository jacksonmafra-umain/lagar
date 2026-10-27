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

# type -> layer
TYPES = {
    "fundamental_law": "fundamental",
    "act": "sfs",
    "ordinance": "sfs",
    "other_statute": "sfs",
}
