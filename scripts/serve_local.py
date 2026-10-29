"""Serve the wasmJs web app and the static API together, fully offline.

    python3 -I scripts/serve_local.py [--build missing|always|never] [--port 8001]

The web app reads `api/v1/` next to its own page (app/README.md, "Data source"),
so one server answers `/api/v1/...` from the built API and every other path
from the web app distribution. Missing builds are made first: the API with
`api/build.py` from `corpus/`, the web app with Gradle.
"""

import argparse
import functools
import http.server
import posixpath
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = ROOT / "build" / "api" / "v1"
DEFAULT_WEB = ROOT / "app" / "webApp" / "build" / "dist" / "wasmJs" / "productionExecutable"
API_PREFIX = "/api/v1/"


def resolve(path, web_dir, api_dir):
    """File for a request path, or None when it leaves both folders."""
    path = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
    clean = posixpath.normpath(path)
    if path.endswith("/") and not clean.endswith("/"):
        clean += "/"
    if clean.startswith(API_PREFIX) or clean == API_PREFIX.rstrip("/"):
        base, rest = Path(api_dir), clean[len(API_PREFIX):]
    else:
        base, rest = Path(web_dir), clean.lstrip("/")
    target = (base / rest).resolve()
    base = base.resolve()
    if target != base and base not in target.parents:
        return None
    if target.is_dir():
        target = target / "index.html"
    return target


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".wasm": "application/wasm", ".js": "text/javascript", ".json": "application/json",
                      ".mjs": "text/javascript"}

    def __init__(self, *args, web_dir, api_dir, **kwargs):
        self.web_dir, self.api_dir = web_dir, api_dir
        super().__init__(*args, directory=str(web_dir), **kwargs)

    def translate_path(self, path):
        target = resolve(path, self.web_dir, self.api_dir)
        return str(target) if target is not None else str(Path(self.web_dir) / "__outside__")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        if self.server.verbose:
            super().log_message(format, *args)


def build_api(api_dir):
    print(f"building the API into {api_dir}", flush=True)
    subprocess.run([sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(ROOT / "corpus"),
                    "--out", str(api_dir)], check=True)


def build_web():
    print("building the web app (Gradle)", flush=True)
    subprocess.run(["./gradlew", ":webApp:wasmJsBrowserDistribution"], cwd=ROOT / "app", check=True)


def ensure_builds(mode, api_dir, web_dir, web_dist=DEFAULT_WEB, run_api=build_api, run_web=build_web):
    """Build what `mode` asks for; return the problems that stop the server (empty when ready)."""
    if mode == "always" or (mode == "missing" and not (api_dir / "index.json").is_file()):
        run_api(api_dir)
    if mode == "always" or (mode == "missing" and not (web_dir / "index.html").is_file()):
        if web_dir.resolve() != web_dist.resolve():
            return [f"{web_dir} has no index.html and is not the Gradle output; build it first"]
        run_web()
    problems = []
    if not (api_dir / "index.json").is_file():
        problems.append(f"no API in {api_dir} (run with --build missing)")
    if not (web_dir / "index.html").is_file():
        problems.append(f"no web app in {web_dir} (run with --build missing)")
    return problems


def make_server(host, port, web_dir, api_dir, verbose=False):
    handler = functools.partial(Handler, web_dir=Path(web_dir), api_dir=Path(api_dir))
    server = http.server.ThreadingHTTPServer((host, port), handler)
    server.verbose = verbose
    return server


def main(argv):
    parser = argparse.ArgumentParser(prog="serve_local.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--build", choices=("missing", "always", "never"), default="missing",
                        help="build the API and the web app when missing (default), always, or never")
    parser.add_argument("--api-dir", type=Path, default=DEFAULT_API)
    parser.add_argument("--web-dir", type=Path, default=DEFAULT_WEB)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--verbose", action="store_true", help="log every request")
    args = parser.parse_args(argv)
    try:
        problems = ensure_builds(args.build, args.api_dir, args.web_dir)
    except subprocess.CalledProcessError as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    server = make_server(args.host, args.port, args.web_dir, args.api_dir, args.verbose)
    print(f"web app: http://{args.host}:{server.server_address[1]}/  (API under {API_PREFIX})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
