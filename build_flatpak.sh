#!/usr/bin/env bash
set -euo pipefail

# Simple Flatpak build/install helper for:
#   Elite: Dangerous Colonization Assistant
#
# This script wraps flatpak-builder using the project's Flatpak manifest:
#   - uk.codecrafter.EDColonizationAssistant.yml
#
# It is intended for developers or advanced users on Linux who want a
# per-user Flatpak install (no custom GUI installer, no Windows tooling).
#
# Requirements:
#   - flatpak
#   - flatpak-builder
#   - Appropriate runtime/SDK remotes configured (e.g. Flathub) that provide:
#       org.freedesktop.Platform//23.08
#       org.freedesktop.Sdk//23.08
#       org.freedesktop.Sdk.Extension.node18//23.08
#
# Typical usage (from the project root):
#   chmod +x build_flatpak.sh
#   ./build_flatpak.sh
#
# On success, the app can be run with:
#   flatpak run uk.codecrafter.EDColonizationAssistant

MANIFEST="uk.codecrafter.EDColonizationAssistant.yml"
APP_ID="uk.codecrafter.EDColonizationAssistant"
BUILDDIR="build-flatpak-edca"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "${SCRIPT_DIR}"

if ! command -v flatpak-builder >/dev/null 2>&1; then
  echo "Error: flatpak-builder is not installed or not on PATH."
  echo "Install flatpak-builder via your distribution's package manager and try again."
  exit 1
fi

if [ ! -f "${MANIFEST}" ]; then
  echo "Error: Flatpak manifest '${MANIFEST}' not found in project root."
  echo "Make sure you are running this script from the Elite: Dangerous Colonization Assistant source tree."
  exit 1
fi

echo "==============================================="
echo " Building Flatpak: ${APP_ID}"
echo " Manifest:         ${MANIFEST}"
echo " Build directory:  ${BUILDDIR}"
echo "==============================================="
echo

flatpak-builder \
  --user \
  --force-clean \
  --install \
  "${BUILDDIR}" \
  "${MANIFEST}"

echo
echo "Done."
echo "You can run the app with:"
echo "  flatpak run ${APP_ID}"