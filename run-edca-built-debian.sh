#!/usr/bin/env bash
set -euo pipefail

# Build + run helper (Linux/macOS) for Elite: Dangerous Colonization Assistant.
#
# What it does:
#  1) Creates/updates a Python venv for backend dependencies.
#  2) Builds the frontend production bundle into frontend/dist (served at /app).
#  3) Starts the backend on http://127.0.0.1:8000
#  4) Opens your default browser at http://127.0.0.1:8000/app/
#
# Usage:
#   chmod +x ./run-edca-built.sh
#   ./run-edca-built.sh
#
# Options via env:
#   EDCA_HOST=127.0.0.1
#   EDCA_PORT=8000
#   EDCA_PYTHON=python3.12               (python executable to create the backend venv)
#   EDCA_VENV_DIR=.venv312               (where to create/use the backend venv; default: backend/.venv)
#   EDCA_RECREATE_VENV=1                 (delete and recreate the venv if Python version mismatch)
#   EDCA_SKIP_FRONTEND_BUILD=1           (skip npm ci/build; assumes frontend/dist exists)
#   EDCA_FORCE_FRONTEND_BUILD=1          (rebuild frontend even if frontend/dist exists)
#   EDCA_SKIP_BACKEND_DEPS=1             (skip pip install -r backend/requirements.txt)
#
# Notes:
#  - This is NOT a Flatpak build. It runs from source on your machine.
#  - You need Python 3.10+.
#  - Node.js/npm are only required when actually building the frontend.

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
    die "Python is required but was not found on PATH. Install Python 3.10+ (recommended: 3.12). You can also set EDCA_PYTHON=python3.12"
  fi
fi

PY_VER="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")' 2>/dev/null || true)"
log "Using Python: ${PYTHON} (${PY_VER})"
# pydantic==2.5.0 pulls pydantic-core which may not have wheels for Python 3.13,
# causing a Rust build requirement (maturin/cargo).
PY_MAJOR_MINOR="$("${PYTHON}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
if [ "${PY_MAJOR_MINOR}" = "3.13" ]; then
  log "WARNING: Python 3.13 detected. backend/requirements.txt pins pydantic==2.5.0, which may require Rust to build pydantic-core on 3.13."
  log "Recommended: install Python 3.12 and run with: EDCA_PYTHON=python3.12 ./run-edca-built.sh"
fi

# Node/npm are only required if we are going to build the frontend.
NEED_FRONTEND_BUILD=1
if [ "${EDCA_SKIP_FRONTEND_BUILD:-0}" = "1" ]; then
  NEED_FRONTEND_BUILD=0
elif [ -d "frontend/dist" ]; then
  # If a production build already exists, default to reusing it unless the user explicitly wants rebuilds.
  # Set EDCA_FORCE_FRONTEND_BUILD=1 to rebuild every time.
  if [ "${EDCA_FORCE_FRONTEND_BUILD:-0}" != "1" ]; then
    NEED_FRONTEND_BUILD=0
  fi
fi
if [ "${NEED_FRONTEND_BUILD}" = "1" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    die "Node.js/npm are required to build the frontend, but were not found on PATH. Either install Node.js (20+ recommended) or set EDCA_SKIP_FRONTEND_BUILD=1 with an existing frontend/dist."
  fi
fi

# ----------------------------- backend venv + deps

VENV_DIR="${EDCA_VENV_DIR:-backend/.venv}"
VENV_PY="${VENV_DIR}/bin/python"
RECREATE_VENV="${EDCA_RECREATE_VENV:-0}"

# If the venv already exists, ensure it matches the requested Python major.minor.
# This prevents the common failure mode where backend/.venv was created earlier with Python 3.13
# and then reused even when EDCA_PYTHON points at 3.12.
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
  log "Installing backend dependencies (pip) ..."

  # Some environments (including some uv-created venvs) may not include pip by default.
  # Bootstrap it before attempting installs.
  if ! "${VENV_PY}" -c "import pip" >/dev/null 2>&1; then
    log "pip not found in venv; bootstrapping via ensurepip ..."
    if ! "${VENV_PY}" -m ensurepip --upgrade >/dev/null 2>&1; then
      die "pip is missing in the venv and ensurepip failed. Try recreating the venv (EDCA_RECREATE_VENV=1) or run: ${VENV_PY} -m ensurepip --upgrade"
    fi
  fi

  "${VENV_PY}" -m pip install --upgrade pip
  "${VENV_PY}" -m pip install -r backend/requirements.txt
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
frontend build exists at frontend/dist (see backend static mount at /app).

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

# Wait until backend + UI are ready (best-effort)
log "Waiting for backend to become ready ..."
"${VENV_PY}" - <<PY
import time
import urllib.request
import urllib.error

base = "http://127.0.0.1:${APP_PORT}"
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