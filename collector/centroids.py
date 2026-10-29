"""Entry point: python3 -I collector/centroids.py <scb-boundaries.zip> [--geo sweden.json]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import centroids  # noqa: E402

if __name__ == "__main__":
    sys.exit(centroids.main(sys.argv[1:]))
