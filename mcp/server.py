"""Entry point: python3 -I mcp/server.py [--api build/api/v1 | URL] [--repo DIR]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lagarmcp import server  # noqa: E402

if __name__ == "__main__":
    sys.exit(server.main(sys.argv[1:]))
