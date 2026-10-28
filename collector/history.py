"""Entry point: python3 -I collector/history.py (--pilot | --number YYYY:N ...) [options].

Writes a `git fast-import` stream of metadata-only history; see lagar/history.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import history  # noqa: E402

if __name__ == "__main__":
    sys.exit(history.main(sys.argv[1:]))
