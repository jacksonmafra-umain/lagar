"""Entry point: python3 -I collector/plan.py [options]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import progress  # noqa: E402

if __name__ == "__main__":
    sys.exit(progress.main(sys.argv[1:]))
