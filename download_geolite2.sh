#!/usr/bin/env bash
#
# download_geolite2.sh — Fetch MaxMind GeoLite2-City database
#
# Requires a free MaxMind license key.
# Sign up at: https://www.maxmind.com/en/geolite2/signup
# Get your license key from: https://www.maxmind.com/en/accounts/current/license-key
#
# Usage:
#   export MAXMIND_LICENSE_KEY="your_key_here"
#   ./download_geolite2.sh
#
# Or put the key in a file:
#   echo "your_key" > .maxmind_key
#   ./download_geolite2.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
KEY_FILE="${SCRIPT_DIR}/.maxmind_key"

# Determine license key
LICENSE_KEY="${MAXMIND_LICENSE_KEY:-}"
if [[ -z "$LICENSE_KEY" && -f "$KEY_FILE" ]]; then
    LICENSE_KEY=$(cat "$KEY_FILE" | tr -d '[:space:]')
fi

if [[ -z "$LICENSE_KEY" ]]; then
    echo "ERROR: No MaxMind license key found."
    echo ""
    echo "Options:"
    echo "  1. Set environment variable: export MAXMIND_LICENSE_KEY=\"your_key\""
    echo "  2. Create file: echo \"your_key\" > ${KEY_FILE}"
    echo ""
    echo "Get a free license key at: https://www.maxmind.com/en/geolite2/signup"
    exit 1
fi

mkdir -p "$DATA_DIR"

echo "Downloading GeoLite2-City database..."
echo "  License key: ${LICENSE_KEY:0:4}****"
echo "  Output: ${DATA_DIR}/GeoLite2-City.mmdb"

# Download the GeoLite2-City tarball
DOWNLOAD_URL="https://download.maxmind.com/geoip/databases/GeoLite2-City/download?suffix=tar.gz"
TARBALL="${DATA_DIR}/geolite2-city.tar.gz"

echo "  Fetching tarball..."
curl -sL -o "$TARBALL" -u "${LICENSE_KEY}:" "$DOWNLOAD_URL"

if [[ ! -s "$TARBALL" ]]; then
    echo "ERROR: Download failed — tarball is empty."
    echo "Check that your license key is valid."
    exit 1
fi

echo "  Extracting..."
tar -xzf "$TARBALL" -C "$DATA_DIR" --strip-components=1 --wildcards "*/GeoLite2-City.mmdb"

# Clean up
rm -f "$TARBALL"

MMDB_PATH="${DATA_DIR}/GeoLite2-City.mmdb"
if [[ -f "$MMDB_PATH" ]]; then
    SIZE=$(du -h "$MMDB_PATH" | cut -f1)
    echo "  Done! Database saved to ${MMDB_PATH} (${SIZE})"
else
    echo "ERROR: Extraction completed but GeoLite2-City.mmdb not found."
    ls -la "$DATA_DIR"
    exit 1
fi