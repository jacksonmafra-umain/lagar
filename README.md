# lagar

Swedish laws, case law, EU law, municipal regulations and public services as
Markdown, one file per norm, with a static JSON API and Compose Multiplatform
apps for Android, iOS and the web.

## Repository layout

- `corpus/` - one YAML-fronted Markdown file per norm
- `collector/` - Python collectors that build the corpus from official sources
- `api/` - generator for the static JSON API served on GitHub Pages
- `app/` - Compose Multiplatform app (Android, iOS, web)
- `docs/` - architecture, API contract and decision records
- `design/` - design exports and references

## Documentation

- [Design system](DESIGN.md)
- [App architecture](docs/architecture.md)
- [API contract](docs/api.md)
- [Notice](NOTICE.md) and [licence](LICENSE)
