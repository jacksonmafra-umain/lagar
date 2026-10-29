"""MCP server over stdio (newline-delimited JSON-RPC 2.0) exposing the lagar API as tools."""

import argparse
import json
import sys
from pathlib import Path

from .store import ApiStore, NotFound, SearchIndex

SERVER_INFO = {"name": "lagar", "version": "0.1.0"}
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS = {"progress": "PROGRESS.md", "coverage": "COVERAGE.md", "agencies": "AGENCIES.md"}
MAX_LIMIT = 100

TOOLS = [
    {
        "name": "search_laws",
        "description": "Full-text search over Swedish laws, ordinances, agency and county regulations, case law, "
                       "EU law and municipal regulations, using the API's per-layer search index. Query terms are "
                       "matched as whole words (å/ä/ö fold to a/a/o; SFS numbers such as 1962:700 are one term); all "
                       "terms must match. Results rank title matches first, then number, then body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Words or a number, e.g. 'brottsbalken' or '1962:700'."},
                "layers": {"type": "array", "items": {"type": "string"},
                           "description": "Limit to these layers (see list_layers), e.g. ['sfs', 'case_law']."},
                "types": {"type": "array", "items": {"type": "string"},
                          "description": "Limit to these document types, e.g. ['act']."},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 20},
                "prefix": {"type": "boolean", "default": False,
                           "description": "Match terms as prefixes (type-ahead), e.g. 'skatt' finds 'skatteverket'."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_document",
        "description": "One document by id (e.g. 'sfs-1962-700', 'afs-2023-1', 'hdo-...'): all metadata and the "
                       "Markdown text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 0, "default": 20000,
                              "description": "Truncate the body to this many characters; 0 returns metadata only."},
            },
            "required": ["id"],
        },
    },
    {
        "name": "list_layers",
        "description": "The normative layers (fundamental, sfs, agency, case_law, eu, region, municipality, service) "
                       "with document counts per type, and the API build time.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_documents",
        "description": "One page (50 items, newest first) of a layer or of one type within a layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string"},
                "type": {"type": "string"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
            },
            "required": ["layer"],
        },
    },
    {
        "name": "get_report",
        "description": "A generated or curated report of the repository: 'progress' (counts per series against "
                       "targets, PROGRESS.md), 'coverage' (what the corpus covers and its known gaps, COVERAGE.md) or "
                       "'agencies' (which agencies and sources are processed and why others are not, AGENCIES.md).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": list(REPORTS)},
                "section": {"type": "string", "description": "Only the section whose heading contains this text."},
            },
            "required": ["name"],
        },
    },
]


class ToolError(Exception):
    """A tool call that failed in a way the client should see (isError)."""


def _section(text, heading):
    """The lines from the first heading containing `heading` up to the next heading of the same or higher level."""
    lines, out, level = text.splitlines(), [], None
    for line in lines:
        depth = len(line) - len(line.lstrip("#")) if line.startswith("#") else 0
        if level is None:
            if depth and heading.lower() in line.lower():
                level = depth
                out.append(line)
        elif depth and depth <= level:
            break
        else:
            out.append(line)
    if level is None:
        raise ToolError(f"no section matching {heading!r}")
    return "\n".join(out) + "\n"


class LagarServer:
    def __init__(self, store, repo_root=REPO_ROOT):
        self.store = store
        self.repo_root = Path(repo_root)
        self._search = None

    # --- tools -------------------------------------------------------------

    def search_laws(self, query, layers=None, types=None, limit=20, prefix=False):
        if not str(query).strip():
            raise ToolError("query is empty")
        if self._search is None:
            try:
                self._search = SearchIndex(self.store)
            except NotFound as error:
                raise ToolError("the API has no search index (search/index.json)") from error
        limit = max(1, min(int(limit), MAX_LIMIT))
        return self._search.search(str(query), layers=layers, types=types, limit=limit, prefix=bool(prefix))

    def get_document(self, id, max_chars=20000):
        try:
            doc = self.store.document(str(id).strip().lower())
        except NotFound as error:
            raise ToolError(f"no document with id {id!r}") from error
        except ValueError as error:
            raise ToolError(str(error)) from error
        body, max_chars = doc["body"], max(0, int(max_chars))
        return {"meta": doc["meta"], "body": body[:max_chars], "body_chars": len(body),
                "truncated": len(body) > max_chars}

    def list_layers(self):
        index = self.store.index()
        return {"built_at": index["built_at"], "layers": index["layers"]}

    def list_documents(self, layer, type=None, page=1):
        try:
            return self.store.listing(layer, type, page)
        except NotFound as error:
            raise ToolError(f"no listing for layer {layer!r}, type {type!r}, page {page}") from error
        except ValueError as error:
            raise ToolError(str(error)) from error

    def get_report(self, name, section=None):
        if name not in REPORTS:
            raise ToolError(f"unknown report {name!r}; one of {', '.join(REPORTS)}")
        path = self.repo_root / REPORTS[name]
        if not path.is_file():
            raise ToolError(f"{REPORTS[name]} is not in this checkout")
        text = path.read_text(encoding="utf-8")
        return {"report": REPORTS[name], "text": _section(text, section) if section else text}

    # --- protocol ----------------------------------------------------------

    def call_tool(self, name, arguments):
        tool = {t["name"] for t in TOOLS}
        if name not in tool:
            raise ToolError(f"unknown tool {name!r}")
        try:
            result = getattr(self, name)(**(arguments or {}))
        except TypeError as error:
            raise ToolError(f"bad arguments for {name}: {error}") from error
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}],
                "isError": False}

    def handle(self, message):
        """Response for one JSON-RPC message, or None for a notification."""
        method, msg_id, params = message.get("method"), message.get("id"), message.get("params") or {}
        if "id" not in message:
            return None
        try:
            if method == "initialize":
                requested = params.get("protocolVersion")
                version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
                result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": SERVER_INFO,
                          "instructions": "Swedish legislation from the lagar static API. Search with search_laws, "
                                          "then read a hit with get_document. Legal text is Swedish; do not "
                                          "present a machine translation as the law."}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                try:
                    result = self.call_tool(params.get("name"), params.get("arguments"))
                except ToolError as error:
                    result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
            else:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"no method {method}"}}
        except (OSError, ValueError, KeyError) as error:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(error)}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def serve(self, stdin=sys.stdin, stdout=sys.stdout):
        for line in stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(error)}}
            else:
                response = self.handle(message) if isinstance(message, dict) else {
                    "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "expected an object"}}
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()


def main(argv):
    parser = argparse.ArgumentParser(prog="server.py", description="MCP server (stdio) for the lagar API.")
    parser.add_argument("--api", default=str(REPO_ROOT / "build" / "api" / "v1"),
                        help="API folder or base URL, e.g. https://jacksonmafra-umain.github.io/lagar/api/v1/ "
                             "(default: build/api/v1 of this checkout)")
    parser.add_argument("--repo", default=str(REPO_ROOT), help="checkout whose PROGRESS.md and COVERAGE.md to serve")
    args = parser.parse_args(argv)
    LagarServer(ApiStore(args.api), args.repo).serve()
    return 0
