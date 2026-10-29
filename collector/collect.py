"""Entry point: python3 -I collector/collect.py {sfs,sfspdf,sfsr,eu} [options]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagar import eu, sfs, sfspdf, sfsr  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "sfspdf":
        sys.exit(sfspdf.main(argv[1:]))
    if argv and argv[0] == "sfsr":
        sys.exit(sfsr.main(argv[1:]))
    if argv and argv[0] == "eu":
        sys.exit(eu.main(argv[1:]))
    sys.exit(sfs.main(argv))
