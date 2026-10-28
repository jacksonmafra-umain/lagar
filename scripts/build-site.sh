#!/usr/bin/env bash
# Assembles the landing page and the wasmJs web app into one static folder for Vercel:
#   <out>/            landing/ (without its tests) and the app fonts
#   <out>/app/        the web app distribution
#
# Environment:
#   LAGAR_SITE_OUT   output folder (default: build/landing)
#   LAGAR_WASM_DIST  use this web app build instead of running Gradle
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
out="${LAGAR_SITE_OUT:-$root/build/landing}"
fonts="$root/app/shared/src/commonMain/composeResources/font"

case "$out" in
  "" | "/" | "$root" | "$HOME") echo "refusing to use $out as the output folder" >&2; exit 1 ;;
esac

dist="${LAGAR_WASM_DIST:-}"
if [ -z "$dist" ]; then
  (cd "$root/app" && ./gradlew :webApp:wasmJsBrowserDistribution)
  dist="$root/app/webApp/build/dist/wasmJs/productionExecutable"
fi
[ -f "$dist/index.html" ] || { echo "no web app build in $dist" >&2; exit 1; }

rm -rf "$out"
mkdir -p "$out/fonts" "$out/app"
(cd "$root/landing" && COPYFILE_DISABLE=1 tar -cf - --exclude ./tests --exclude .DS_Store .) | tar -xf - -C "$out"
cp "$fonts"/*.ttf "$out/fonts/"
cp -R "$dist/." "$out/app/"

echo "$out"
