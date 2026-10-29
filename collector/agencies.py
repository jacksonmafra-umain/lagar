"""Entry point: python3 -I collector/agencies.py [--refresh] [options]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import agencies  # noqa: E402

if __name__ == "__main__":
    sys.exit(agencies.main(sys.argv[1:]))
