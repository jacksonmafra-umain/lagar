#!/usr/bin/env bash
# Assembles the landing page into one static folder for Vercel:
#   <out>/                     landing/ (without its tests) and the app fonts
#   <out>/data/statistics.json the corpus statistics the page shows (collector/stats.py)
#
# Environment:
#   LAGAR_SITE_OUT   output folder (default: build/landing)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
out="${LAGAR_SITE_OUT:-$root/build/landing}"
fonts="$root/app/shared/src/commonMain/composeResources/font"
stats="$root/collector/data/statistics.json"

case "$out" in
  "" | "/" | "$root" | "$HOME") echo "refusing to use $out as the output folder" >&2; exit 1 ;;
esac

[ -f "$stats" ] || { echo "no statistics in $stats; run collector/stats.py" >&2; exit 1; }

rm -rf "$out"
mkdir -p "$out/fonts"
(cd "$root/landing" && COPYFILE_DISABLE=1 tar -cf - --exclude ./tests --exclude .DS_Store .) | tar -xf - -C "$out"
cp "$fonts"/*.ttf "$out/fonts/"
mkdir -p "$out/data"
cp "$stats" "$out/data/statistics.json"

echo "$out"
