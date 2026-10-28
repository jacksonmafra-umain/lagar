"""Entry point: python3 -I collector/collect.py sfs [options]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import sfs  # noqa: E402

if __name__ == "__main__":
    sys.exit(sfs.main(sys.argv[1:]))
