#!/bin/sh
# #37: turn the SVG sources in branding/ into the PNG icons and link preview
# image the app serves. Run by hand from the repo root after changing an SVG:
#
#   sh branding/build.sh
#
# Uses sips, which is built into macOS, so no extra package is needed. sips
# draws each SVG at the size it declares, and -z then resizes the result.
# The PNGs land in the app's static folder, where WhiteNoise serves them;
# commit them along with the SVG change. (Like app.css, they're built here,
# not on Railway.)
set -e
cd "$(dirname "$0")"
OUT=../heritage_media_availability/static/heritage_media_availability

# Browser tab icon (team pages and admin): 32x32, rounded corners built in.
sips -s format png icon.svg --out "$OUT/favicon-32.png" >/dev/null
sips -z 32 32 "$OUT/favicon-32.png" >/dev/null

# iPhone home-screen icon: 180x180, square (iOS rounds the corners).
sips -s format png icon-full-bleed.svg --out "$OUT/apple-touch-icon.png" >/dev/null
sips -z 180 180 "$OUT/apple-touch-icon.png" >/dev/null

# Link preview (og:image): drawn at its full 1200x630, no resizing.
sips -s format png link-preview.svg --out "$OUT/link-preview.png" >/dev/null

echo "Built favicon-32.png, apple-touch-icon.png and link-preview.png in $OUT"
