#!/usr/bin/env bash
set -euo pipefail

# UNTESTED: Arch Linux build + run helper for Elite: Dangerous Colonization Assistant.
#
# This is a convenience wrapper around the same workflow as
# [`run-edca-built-debian.sh`](run-edca-built-debian.sh:1), but with Arch-specific hints.
#
# Arch prerequisite hints (not performed automatically):
#   - Install base tools:
#       sudo pacman -Syu --needed curl ca-certificates
#   - Optional Node.js/npm (only needed if you want to build frontend/dist locally):
#       sudo pacman -Syu --needed nodejs npm
#   - Consider using uv-managed Python 3.12 to avoid source builds on newer system Pythons.
#
# Usage:
#   chmod +x ./run-edca-built-arch.sh
#   EDCA_PYTHON=python3.12 EDCA_VENV_DIR=.venv312 ./run-edca-built-arch.sh
#
# Options via env (same as [`run-edca-built-debian.sh`](run-edca-built-debian.sh:1)):
#   EDCA_HOST, EDCA_PORT, EDCA_PYTHON, EDCA_VENV_DIR, EDCA_RECREATE_VENV,
#   EDCA_SKIP_FRONTEND_BUILD, EDCA_FORCE_FRONTEND_BUILD, EDCA_SKIP_BACKEND_DEPS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "${SCRIPT_DIR}"

APP_HOST="${EDCA_HOST:-127.0.0.1}"
APP_PORT="${EDCA_PORT:-8000}"
UI_URL="http://${APP_HOST}:${APP_PORT}/app/"

log() { printf '%s\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

# ----------------------------- prerequisites

PYTHON="${EDCA_PYTHON:-python3}"
if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  if [ -z "${EDCA_PYTHON:-}" ] && command -v python >/dev/null 2>&1; then
    PYTHON="python"
  else
    die "Python is required but was not found on PATH. Install Python 3.10+ (recommended: 3.12 via uv)."
  fi
fi

PY_VER="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || true)"
log "Using Python: ${PYTHON} (${PY_VER})"

if ! command -v uv >/dev/null 2>&1; then
  die "uv is required but was not found on PATH. Install uv (https://docs.astral.sh/uv/) and ensure it's on PATH (often: export PATH=\"\$HOME/.local/bin:\$PATH\")."
fi

PY_MAJOR_MINOR="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
if [ "${PY_MAJOR_MINOR}" = "3.13" ]; then
  log "WARNING: Python 3.13 detected. backend/requirements.txt pins pydantic==2.5.0, which may require Rust to build pydantic-core on 3.13."
  log "Recommended: install Python 3.12 via uv and run with: EDCA_PYTHON=python3.12 EDCA_VENV_DIR=.venv312 ./run-edca-built-arch.sh"
fi

# Node/npm are only required if we are going to build the frontend.
NEED_FRONTEND_BUILD=1
if [ "${EDCA_SKIP_FRONTEND_BUILD:-0}" = "1" ]; then
  NEED_FRONTEND_BUILD=0
elif [ -d "frontend/dist" ]; then
  if [ "${EDCA_FORCE_FRONTEND_BUILD:-0}" != "1" ]; then
    NEED_FRONTEND_BUILD=0
  fi
fi

if [ "${NEED_FRONTEND_BUILD}" = "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    die "Node.js/npm are required to build the frontend, but were not found on PATH. Install nodejs/npm or set EDCA_SKIP_FRONTEND_BUILD=1 with an existing frontend/dist."
  fi
fi

# ----------------------------- backend venv + deps

VENV_DIR="${EDCA_VENV_DIR:-backend/.venv}"
VENV_PY="${VENV_DIR}/bin/python"
RECREATE_VENV="${EDCA_RECREATE_VENV:-0}"

if [ -x "${VENV_PY}" ]; then
  VENV_MAJOR_MINOR="$("${VENV_PY}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [ -n "${PY_MAJOR_MINOR:-}" ] && [ -n "${VENV_MAJOR_MINOR}" ] && [ "${VENV_MAJOR_MINOR}" != "${PY_MAJOR_MINOR}" ]; then
    if [ "${RECREATE_VENV}" = "1" ]; then
      log "Venv at ${VENV_DIR} uses Python ${VENV_MAJOR_MINOR}, but requested ${PY_MAJOR_MINOR}; recreating (EDCA_RECREATE_VENV=1) ..."
      rm -rf "${VENV_DIR}"
    else
      die "Venv at ${VENV_DIR} uses Python ${VENV_MAJOR_MINOR}, but requested ${PY_MAJOR_MINOR}. Set EDCA_RECREATE_VENV=1 to recreate it, or set EDCA_VENV_DIR to a different venv (e.g. .venv312)."
    fi
  fi
fi

if [ ! -x "${VENV_PY}" ]; then
  log "Creating backend virtualenv at ${VENV_DIR} using ${PYTHON} ..."
  "${PYTHON}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

if [ "${EDCA_SKIP_BACKEND_DEPS:-0}" != "1" ]; then
  if [ ! -f "backend/requirements.txt" ]; then
    die "backend/requirements.txt not found."
  fi

  log "Installing backend dependencies (uv pip) ..."
  uv pip install -r backend/requirements.txt
else
  log "Skipping backend dependency install (EDCA_SKIP_BACKEND_DEPS=1)."
fi

# ----------------------------- frontend build

if [ "${NEED_FRONTEND_BUILD}" = "1" ]; then
  if [ ! -f "frontend/package-lock.json" ]; then
    die "frontend/package-lock.json not found (expected for reproducible builds)."
  fi
  log "Installing frontend dependencies (npm ci) ..."
  npm --prefix frontend ci --no-audit --no-fund
  log "Building frontend production bundle (vite build) ..."
  npm --prefix frontend run build --no-audit --no-fund
else
  if [ "${EDCA_SKIP_FRONTEND_BUILD:-0}" = "1" ]; then
    log "Skipping frontend build (EDCA_SKIP_FRONTEND_BUILD=1)."
  else
    log "Skipping frontend build (reusing existing frontend/dist)."
  fi
fi

if [ ! -d "frontend/dist" ]; then
  cat >&2 <<'EOF'
Error: frontend/dist not found.

This script opens the UI at /app/, which is served by the backend only when a production
frontend build exists at frontend/dist.

Fix options:
  1) Build the frontend once (requires Node/npm):
       npm --prefix frontend ci
       npm --prefix frontend run build

  2) Copy a prebuilt frontend/dist from another machine/CI build into ./frontend/dist

If you intentionally skipped the frontend build, unset EDCA_SKIP_FRONTEND_BUILD or provide frontend/dist.
EOF
  exit 1
fi

# ----------------------------- run backend + open browser

log "Starting backend on http://${APP_HOST}:${APP_PORT} (UI: ${UI_URL}) ..."
set +e
"${VENV_PY}" -m uvicorn backend.src.main:app --host "${APP_HOST}" --port "${APP_PORT}" &
BACKEND_PID=$!
set -e

cleanup() {
  log ""
  log "Stopping backend (PID ${BACKEND_PID}) ..."
  kill "${BACKEND_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "Waiting for backend to become ready ..."
"${VENV_PY}" - <<PY
import time
import urllib.request

base = "http://${APP_HOST}:${APP_PORT}"
urls = [f"{base}/api/health", f"{base}/app/"]
deadline = time.time() + 60

def ok(u: str) -> bool:
    try:
        with urllib.request.urlopen(u, timeout=2) as r:
            return 200 <= r.getcode() < 500
    except Exception:
        return False

while time.time() < deadline:
    if all(ok(u) for u in urls):
        break
    time.sleep(0.5)
PY

log "Opening browser: ${UI_URL}"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${UI_URL}" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "${UI_URL}" >/dev/null 2>&1 || true
else
  "${VENV_PY}" - <<PY
import webbrowser
webbrowser.open("${UI_URL}")
PY
fi

log "Backend is running. Press Ctrl+C to stop."
wait "${BACKEND_PID}"