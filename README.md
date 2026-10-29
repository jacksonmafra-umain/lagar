# lagar

Swedish laws, case law, EU law, municipal regulations and public services as
Markdown, one file per norm, with a static JSON API and Compose Multiplatform
apps for Android, iOS and the web.

Website: <https://grundlagar.vercel.app> (the web app is at `/app/`).

## Repository layout

- `corpus/` - one YAML-fronted Markdown file per norm
- `collector/` - Python collectors that build the corpus from official sources
- `api/` - generator for the static JSON API served on GitHub Pages
- `app/` - Compose Multiplatform app (Android, iOS, web)
- `mcp/` - MCP server that searches and reads the API
- `landing/` - static landing page (Swedish and English), deployed to Vercel with the web app
- `docs/` - architecture, API contract and decision records
- `design/` - design exports and references

## Documentation

- [Progress](PROGRESS.md) and [coverage](COVERAGE.md)
- [Design system](DESIGN.md)
- [App architecture](docs/architecture.md)
- [API contract](docs/api.md)
- [Notice](NOTICE.md) and [licence](LICENSE)

## Local tools

Run the web app fully offline against the local corpus. The script builds the API and the
wasmJs app when they are missing (the web build needs JDK 21), then serves both from one server:

```sh
python3 -I scripts/serve_local.py   # http://127.0.0.1:8001/
```

Search and read the corpus from an MCP client (Claude Code, Claude Desktop and others) with the
stdio server in `mcp/`, standard library only. `.mcp.json` registers it for this checkout against
`build/api/v1` (`python3 -I api/build.py --corpus corpus --out build/api/v1` first); pass the
published API instead to skip the build:

```json
{
  "mcpServers": {
    "lagar": {
      "command": "python3",
      "args": ["-I", "mcp/server.py", "--api", "https://jacksonmafra-umain.github.io/lagar/api/v1/"]
    }
  }
}
```

Tools: `search_laws` (full-text search with the per-layer index, filters by layer and type),
`get_document` (metadata and text by id), `list_layers`, `list_documents` (paged listings) and
`get_report` (progress, coverage and the agencies log).
