#!/usr/bin/env bash
set -euo pipefail

readonly GND_ONTOLOGY_URL="https://d-nb.info/standards/elementset/gnd"
readonly OUTPUT_PATH="docs/gndo.html"

mkdir -p "$(dirname "$OUTPUT_PATH")"

tmp_file="$(mktemp "${OUTPUT_PATH}.XXXXXX")"
trap 'rm -f "$tmp_file"' EXIT

# Request the human-readable ontology documentation page.
curl --fail --location --silent --show-error \
  --header 'Accept: text/html' \
  "$GND_ONTOLOGY_URL" \
  --output "$tmp_file"

mv "$tmp_file" "$OUTPUT_PATH"
trap - EXIT

echo "Saved GND ontology documentation to $OUTPUT_PATH"
