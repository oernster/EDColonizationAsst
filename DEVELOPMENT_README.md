## Production release: building the Windows installer

This section summarises the end-to-end steps to produce a **production-ready**
Windows installer (`EDColonizationAsstInstaller.exe`) that:

- Installs EDCA under a user-writable directory (no admin required by default).
- Ships a self-contained runtime executable (`EDColonizationAsst.exe`) with an
  embedded Python interpreter and backend dependencies.
- Serves the pre-built frontend from FastAPI at `http://127.0.0.1:8000/app/`.
- Does **not** require end users to install Python or Node.js.

These steps are intended for **developers** preparing a release.

### 1. Prerequisites (developer machine)

On the machine where you build the installer:

- Python 3.12+ installed and on `PATH`.
- [`uv`](https://docs.astral.sh/uv/getting-started/) installed.
- Node.js + npm installed (for building the frontend only).
- A working C/C++ toolchain suitable for Nuitka (e.g. MSVC or mingw-w64 via
  the toolchain you’ve already configured).

### 2. Backend dependencies (dev environment)

From the **`backend/`** directory:

```bash
cd backend
uv venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

uv pip install -r requirements-dev.txt
```

This installs all backend + installer build dependencies into a local venv.

### 3. Build the frontend bundle (Vite/React)

From the **`frontend/`** directory:

```bash
cd frontend
npm install
npm run build
cd ..
```

Notes:

- `npm run build` produces `frontend/dist`, which is served by FastAPI at
  `/app`. Vite is configured with `base: '/app/'` so assets resolve under
  `/app/assets/...`.

### 4. Build the runtime EXE (embedded Python backend)

From the **project root** (`c:/Users/Oliver/Development/EDColonizationAsst`):

```bash
uv run python buildruntime.py
```

This runs [`buildruntime.py`](buildruntime.py:1), which:

- Uses Nuitka to compile [`backend/src/runtime_entry.py`](backend/src/runtime_entry.py:1)
  into a single-file EXE:
  - `EDColonizationAsst.exe` (in the project root).
- The EXE embeds:
  - Python runtime.
  - Backend code and dependencies.
- At runtime, it:
  - Starts the FastAPI app in-process on `http://127.0.0.1:8000`.
  - Serves `frontend/dist` at `http://127.0.0.1:8000/app/`.
  - Shows a tray icon with “Open Web UI” and “Exit”.

End users do **not** need Python installed when launched via this EXE.

### 5. Build the GUI installer EXE

Still from the **project root**:

```bash
uv run python buildguiinstaller.py
```

This runs [`buildguiinstaller.py`](buildguiinstaller.py:40), which:

- Ensures `frontend/dist` exists (and runs `npm run build` if not).
- Rebuilds the curated payload tree under `build_payload/`:
  - Includes:
    - `backend/` (with `.py` renamed to `.py_`).
    - `frontend/` (including `dist/`).
    - `run-edca.bat`, `EDColonizationAsst.ico`, `LICENSE`.
    - `EDColonizationAsst.exe` (runtime EXE created in step 4).
- Builds the PySide6 GUI installer via Nuitka from [`guiinstaller.py`](guiinstaller.py:1):
  - Output: `EDColonizationAsstInstaller.exe` in the project root.

### 6. Verify the installer (smoke test)

On a Windows test machine:

1. Copy `EDColonizationAsstInstaller.exe` to the machine.
2. Run it and choose **Install**:
   - Default install directory should be:
     - `%LOCALAPPDATA%\EDColonizationAssistant`
3. After install, check that the install directory contains:
   - `EDColonizationAsst.exe`
   - `backend/`, `frontend/` (with `frontend/dist`).
4. Launch EDCA via the Start Menu / Desktop shortcut:
   - The shortcut should point to `EDColonizationAsst.exe`.
   - A tray icon should appear.
   - The browser should open `http://127.0.0.1:8000/app/` and load the UI.
   - No system Python or Node.js should be required.

If all of the above succeeds, `EDColonizationAsstInstaller.exe` is ready to be
shipped as a production installer.

---

## Project layout

- Root project docs:
  - [`ARCHITECTURE.md`](ARCHITECTURE.md:1) – high-level system and component design
  - [`PROJECT_SETUP.md`](PROJECT_SETUP.md:1) – additional notes and setup details
- Backend (FastAPI, Python): see **Backend development** below
- Frontend (React + TypeScript): see **Frontend development** below

---

## Backend development (FastAPI, Python)

Python FastAPI backend for the Elite: Dangerous Colonization Assistant.

### Setup

Run these commands from the **`backend/` directory** unless otherwise noted.

1. **Install `uv` (once per machine):**

   Follow the official instructions at https://docs.astral.sh/uv/getting-started/
   (for example, via `pipx install uv` on Windows, or your preferred package manager).

2. **Create a virtual environment with `uv`:**

   ```bash
   uv venv .venv
   ```

3. **Activate the virtual environment:**

   ```bash
   # Windows (PowerShell or cmd)
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install dependencies with `uv`:**

   ```bash
   uv pip install -r requirements-dev.txt
   ```

4. **Configure base settings:**

   - Edit `config.yaml` to match your Elite: Dangerous installation.
   - Default journal path is typically:

     ```text
     C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous
     ```

   - See **Configuration** below for full details.

### Commander / Inara configuration

Commander-specific and Inara secrets live in [`backend/commander.yaml`](backend/commander.yaml:1). Example:

```yaml
inara:
  app_name: "ED Colonization Assistant"
  api_key: "INARA-API-KEY-GOES-HERE"
  commander_name: "CMDR Example"
```

Notes:

- Do **not** commit your real API key or commander name; `backend/commander.yaml` is ignored via [`.gitignore`](.gitignore:1).
- You can populate this file in two ways:
  - Via the **Settings** page in the UI (Inara API Key + Commander Name fields), which will write/update `backend/commander.yaml` for you.
  - By creating/editing `backend/commander.yaml` manually using the structure above.
- An example template is provided at [`backend/example.commander.yaml`](backend/example.commander.yaml:1).

### Running the backend

From the **`backend/` directory**:

#### Development server

```bash
uvicorn src.main:app --reload
```

or, from the **project root**:

```bash
uvicorn backend.src.main:app --reload
```

The API will be available at:

- REST API: `http://localhost:8000`
- API docs (Swagger): `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/ws/colonization`

#### Production server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

(or the equivalent `backend.src.main:app` invocation from the project root).

### Testing (backend)

From the **`backend/` directory**, with your virtual environment activated:

- To run the full backend test suite:

  ```bash
  pytest
  ```

- To run with coverage and see missing lines in the terminal:

  ```bash
  pytest --cov=src --cov-report=term-missing
  ```

- To generate an HTML coverage report (open `backend/htmlcov/index.html` in a browser):

  ```bash
  pytest --cov=src --cov-report=html
  ```

- To run a specific test file (for example, the models tests):

  ```bash
  pytest tests/unit/test_models.py -v
  ```

### Code quality (backend)

From the **`backend/` directory**:

#### Format code

```bash
black src/ tests/
isort src/ tests/
```

#### Type checking

```bash
mypy src/
```

#### Linting

```bash
pylint src/
```

### Backend project structure

```text
backend/
├── src/
│   ├── models/          # Data models (Pydantic)
│   ├── services/        # Business logic
│   ├── repositories/    # Data access
│   ├── api/             # API endpoints
│   ├── utils/           # Utilities
│   ├── config.py        # Configuration
│   └── main.py          # Application entry point
├── tests/
│   ├── unit/            # Unit tests
│   └── conftest.py      # Test fixtures
├── requirements.txt      # Production dependencies
└── requirements-dev.txt  # Development dependencies
```

### Backend API overview

The backend exposes REST endpoints and a WebSocket. Key routes (actual implementation in [`backend/src/api/routes.py`](backend/src/api/routes.py:1)):

#### REST

- `GET /api/health` – health check.
- `GET /api/systems` – list all systems with construction sites known locally.
- `GET /api/systems/current` – get current player system and (if docked) station.
- `GET /api/system?name={system_name}` – get colonization data for a specific system.
- `GET /api/system/commodities?name={system_name}` – get aggregated commodities (system shopping list).
- `GET /api/sites` – get all construction sites, categorized by status.
- `GET /api/sites/{market_id}` – get a specific construction site.
- `GET /api/stats` – overall statistics.
- `POST /api/debug/reload-journals` – debug endpoint to re-parse journals from disk.
- Settings & journal:
  - `GET /api/settings`, `POST /api/settings` – get/update app settings (including journal directory and Inara config).
  - `GET /api/journal/status` – minimal view of the current system from journal files.

#### WebSocket

`WS /ws/colonization` – real-time updates (see [`backend/src/api/websocket.py`](backend/src/api/websocket.py:1) for full details).

Typical message flow:

- **Subscribe to system:**

  ```json
  {
    "type": "subscribe",
    "system_name": "LHS 1234"
  }
  ```

- **Unsubscribe from system:**

  ```json
  {
    "type": "unsubscribe",
    "system_name": "LHS 1234"
  }
  ```

- **Update notification (server → client):**

  ```json
  {
    "type": "update",
    "system_name": "LHS 1234",
    "data": {
      "construction_sites": [...],
      "total_sites": 2,
      "completed_sites": 1,
      "in_progress_sites": 1,
      "completion_percentage": 50.0
    },
    "timestamp": "2025-11-29T01:00:00Z"
  }
  ```

### Backend architecture

The backend follows SOLID principles and a clean layered approach:

- **Models** – Pydantic models for data validation and serialization.
- **Services** – business logic:
  - Journal parser
  - File watcher
  - System tracker
  - Data aggregator
  - Inara service wrapper
- **Repositories** – data access layer (SQLite persistence via [`ColonizationRepository`](backend/src/repositories/colonization_repository.py:65)).
- **API** – REST and WebSocket endpoints.

Key components:

1. **Journal Parser** – parses Elite: Dangerous journal files and emits typed events.
2. **File Watcher** – monitors the journal directory and re-parses on change.
3. **System Tracker** – tracks the commander’s current system and station.
4. **Data Aggregator** – merges local journal data (and, in future, Inara data) into system/site summaries.
5. **Repository** – thread-safe, lock-protected access to persisted colonization data in SQLite.
6. **WebSocket Manager** – manages client connections and broadcasts updates on system changes.

### Backend configuration

Main non-sensitive config is in [`backend/config.yaml`](backend/config.yaml:1):

```yaml
journal:
  directory: "C:\\Users\\%USERNAME%\\Saved Games\\Frontier Developments\\Elite Dangerous"
  watch_interval: 1.0

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:5173"

websocket:
  ping_interval: 30
  reconnect_attempts: 5

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

Commander/Inara settings are stored separately in [`backend/commander.yaml`](backend/commander.yaml:1); see **Commander / Inara configuration** above.

### Backend troubleshooting

- **Journal files not found**
  - Verify the path in `backend/config.yaml`.
  - Ensure Elite: Dangerous has been run at least once.
  - Check that the directory exists and is accessible.

- **Import errors**
  - Ensure the virtual environment is activated.
  - Run `uv pip install -r requirements-dev.txt` from the `backend/` directory.

- **Tests failing**
  - Check Python version (3.10+ recommended).
  - Ensure all dependencies are installed.
  - Run `pytest -v` for detailed output.

---

## Frontend development (React + TypeScript)

React + TypeScript frontend for the Elite: Dangerous Colonization Assistant.

### Setup

Run these commands from the **`frontend/` directory**.

1. **Install dependencies:**

   ```bash
   npm install
   ```

2. **Backend proxy / configuration:**

   - The frontend is configured to proxy API requests to `http://localhost:8000`.
   - Ensure the backend is running before starting the frontend (see backend section above).

### Running the frontend

From the **`frontend/` directory**:

#### Development server

```bash
npm run dev
```

The application will be available at:

- `http://localhost:5173`

#### Production build

```bash
npm run build
npm run preview
```

### Testing (frontend)

From the **`frontend/` directory**:

#### Run tests

```bash
npm test
```

#### Run tests with UI

```bash
npm run test:ui
```

#### Run tests with coverage

```bash
npm run test:coverage
```

### Frontend code quality

From the **`frontend/` directory**:

#### Type checking

```bash
npm run type-check
```

#### Linting

```bash
npm run lint
```

### Frontend project structure

```text
frontend/
├── src/
│   ├── components/      # React components
│   │   ├── SystemSelector/
│   │   └── SiteList/
│   ├── stores/          # Zustand state management
│   ├── services/        # API services
│   ├── types/           # TypeScript types
│   ├── App.tsx          # Main application
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── public/              # Static assets
├── index.html           # HTML template
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
└── vite.config.ts       # Vite config
```

### Frontend features

- **System Selector** – dropdown of all known colonization systems (from journal data) with client-side autocomplete.
- **System View**:
  - System-level shopping list of commodities (aggregated across all sites in the selected system).
  - Per-station view: tabs for each construction site with detailed commodity progress.
- **Settings** – configure journal directory and Inara details, persisted to backend config files.
- **Color-coded status** – green for completed, orange for in-progress, etc.
- **Responsive design** – layout tuned for desktop; works on smaller screens.

### Frontend technologies

- **React 18** – UI framework.
- **TypeScript** – static typing.
- **Material-UI (MUI)** – component library.
- **Zustand** – state management.
- **Axios** – HTTP client.
- **Vite** – dev server and build tool.

### Frontend troubleshooting

- **Blank page**
  - Ensure backend is running on port `8000`.
  - Check the browser console for errors.
  - Verify `npm install` completed successfully.

- **API connection errors**
  - Verify backend is accessible at `http://localhost:8000`.
  - Check CORS settings in backend.
  - Ensure proxy configuration in `vite.config.ts` is correct.

- **Build errors**
  - Clear node_modules and lockfile:
    ```bash
    rm -rf node_modules package-lock.json
    npm install
    ```
  - Check Node.js version (18+ recommended).

---

## Running the application (developer view)

This section is aimed at **developers**. For a simplified, non‑technical quick start, see [`README.md`](README.md).

### Root‑level launch scripts

From the **project root**, you can use the same scripts that non‑developers use:

- Windows: [`run-edca.bat`](run-edca.bat)
- Linux / macOS: [`run-edca.sh`](run-edca.sh)

These scripts will:

- Ensure Python backend dependencies from [`backend/requirements.txt`](backend/requirements.txt:1) are installed.
- Ensure frontend dependencies in [`frontend/package.json`](frontend/package.json:1) are installed.
- Start the backend API (FastAPI + Uvicorn) on `http://localhost:8000`.
- Start the frontend (Vite + React) on `http://localhost:5173`.

They are convenient for quick local runs, smoke tests and demos.

### Manual launch from project root

If you prefer explicit commands but don’t want to `cd` into subfolders, you can start both services from the **project root**:

```bash
# Terminal 1 – backend (FastAPI, reload for development)
uvicorn backend.src.main:app --reload
```

Backend will be available at:

- API:  http://localhost:8000
- Docs: http://localhost:8000/docs
- WS:   ws://localhost:8000/ws/colonization

```bash
# Terminal 2 – frontend (Vite + React)
npm --prefix frontend run dev
```

Frontend will be available at:

- http://localhost:5173

These commands are essentially what the launch scripts wrap, but without dependency checks.

### Manual launch from subdirectories

For more traditional workflows:

- Backend: see **Backend development** above (run from [`backend/`](backend:1), usually with a virtualenv).
- Frontend: see **Frontend development** above (run from [`frontend/`](frontend:1)).

Those sections show `uvicorn src.main:app --reload` and `npm run dev` from within each subproject.

## Windows GUI installer build (current pipeline)

This section documents the concrete Windows build pipeline that produces the
self-contained GUI installer executable (`EDColonizationAsstInstaller.exe`)
using Nuitka and the PySide6-based installer UI in
[`guiinstaller.py`](guiinstaller.py:1).

The resulting installer:

- Installs EDCA into a **user-writable directory** under
  `%LOCALAPPDATA%\EDColonizationAssistant` by default (no elevation required).
- Ships:
  - Python backend + virtualenv bootstrap logic.
  - Pre-built frontend assets (`frontend/dist`) served by the backend.
  - A GUI launcher ([`backend/src/launcher.py`](backend/src/launcher.py:173))
    which starts the tray and backend, then opens the web UI.
- Does **not** require Node.js/npm on the end-user machine at runtime.

### Prerequisites (developer machine)

On the **developer** machine (where you build the installer):

- Python 3.12+ installed and on `PATH`.
- [`uv`](https://docs.astral.sh/uv/getting-started/) installed.
- Node.js + npm installed (for building the frontend only).
- Python dependencies installed (from the project root or `backend/`):

  ```bash
  # From backend/ (recommended)
  cd backend
  uv venv .venv
  .venv\Scripts\activate   # or source .venv/bin/activate on Unix
  uv pip install -r requirements-dev.txt
  ```

  The dev requirements include FastAPI, PySide6, and other libraries used by
  the backend and installer.

### 1. Build the frontend (Vite/React)

From the **`frontend/`** directory:

```bash
cd frontend
npm install
npm run build
```

- `npm install` – installs frontend dependencies as declared in
  [`frontend/package.json`](frontend/package.json:1).
- `npm run build` – runs `tsc && vite build`, producing a static bundle in
  `frontend/dist/`.

Notes:

- Tests under `src/**/*.test.tsx` are **excluded** from the production
  TypeScript build via [`tsconfig.json`](frontend/tsconfig.json:1), so you
  don’t need Jest typings just to build.
- Re-run `npm run build` whenever you change frontend code and before
  rebuilding the installer.

### 2. Build the GUI installer executable

From the **project root** (`c:/Users/Oliver/Development/EDColonizationAsst`):

```bash
uv run python buildguiinstaller.py
```

This runs [`build_installer()`](buildguiinstaller.py:40), which:

1. Rebuilds a curated payload tree under `build_payload/` via
   [`_ensure_payload_dir`](buildguiinstaller.py:141):

   - Copies `backend/` and `frontend/`, including `frontend/dist/`.
   - Excludes dev artefacts such as `.git`, `.venv`, `node_modules`,
     `__pycache__`, tests, coverage output, etc.
   - Renames backend `*.py` files in `build_payload/backend/src` to `*.py_`
     so Nuitka doesn’t treat them as importable modules rather than data.

2. Writes a `VERSION` file from [`backend/src/__init__.py`](backend/src/__init__.py:1)
   so the installer can display the correct version in its UI.

3. Invokes Nuitka with the PySide6 plugin to compile
   [`guiinstaller.py`](guiinstaller.py:1) into a single-file executable:

   - Includes the `build_payload` directory as bundled data:
     `--include-data-dir=build_payload=payload`.
   - Bundles `LICENSE` and `VERSION` alongside the executable.

On success, it produces:

- `EDColonizationAsstInstaller.exe` in the **project root**.

### 3. Install / repair using the GUI installer

Run `EDColonizationAsstInstaller.exe` on Windows:

- The default install directory (shown in the installer window) is:

  ```text
  %LOCALAPPDATA%\EDColonizationAssistant
  ```

  This is computed by [`get_default_install_dir()`](guiinstaller.py:154) and
  avoids `C:\Program Files\...` so that standard (non-admin) accounts can
  install and run EDCA without elevation.

- Actions:

  - **Install** – copies the curated payload from `payload/` into the install
    directory, restoring backend `*.py_` back to `*.py` via
    [`InstallerWindow._copy_tree`](guiinstaller.py:781), and (on Windows)
    creates Start Menu / Desktop shortcuts and an Add/Remove Programs entry.
  - **Repair** – overwrites files from the bundled payload into the existing
    install directory and recreates shortcuts if needed.
  - **Uninstall** – stops the tray (via `tray.pid` and `taskkill`), removes
    the install directory, removes shortcuts, and unregisters the app.

### 4. Runtime behaviour of the installed app

After installation:

- The Start Menu / Desktop shortcuts point to a small VBScript launcher
  (`run-edca-hidden.vbs`), which runs [`run-edca.bat`](run-edca.bat:1)
  **without** showing a console window.

- [`run-edca.bat`](run-edca.bat:1):

  - Logs to `run-edca.log` in the install directory.
  - Ensures Python is available.
  - Starts the PySide6 GUI launcher:

    ```bat
    python backend\src\launcher.py
    ```

- [`Launcher`](backend/src/launcher.py:173):

  - Detects the install root.
  - Ensures `backend/venv` exists and installs backend dependencies from
    [`backend/requirements.txt`](backend/requirements.txt:1) into it.
  - Starts the tray controller
    ([`backend/src/tray_app.py`](backend/src/tray_app.py:49)) using the venv
    Python.
  - Waits for the backend to become available at:

    - `http://127.0.0.1:8000/api/health`
    - `http://127.0.0.1:8000/app/`

  - Once ready, enables the “Open Web UI” button, which opens:

    ```text
    http://127.0.0.1:8000/app/
    ```

- [`main.py`](backend/src/main.py:1) mounts the pre-built frontend as static
  files:

  ```python
  from fastapi.staticfiles import StaticFiles

  PROJECT_ROOT = Path(__file__).resolve().parents[2]
  frontend_dist = PROJECT_ROOT / "frontend" / "dist"

  if frontend_dist.exists():
      app.mount(
          "/app",
          StaticFiles(directory=frontend_dist, html=True),
          name="frontend",
      )
  ```

  This means:

  - The frontend is served directly by FastAPI from the bundled `dist/`
    assets.
  - No Vite dev server (`npm run dev`) is started at runtime.
  - End users do **not** need Node.js or npm installed at all.

### 5. Summary of the full Windows build → install → run flow

Developer steps:

1. Backend dev dependencies:

   ```bash
   cd backend
   uv venv .venv
   .venv\Scripts\activate      # or Unix equivalent
   uv pip install -r requirements-dev.txt
   ```

2. Frontend build:

   ```bash
   cd ../frontend
   npm install
   npm run build
   ```

3. Build installer:

   ```bash
   cd ..
   uv run python buildguiinstaller.py
   ```

4. Ship/execute `EDColonizationAsstInstaller.exe`.

User steps:

1. Run `EDColonizationAsstInstaller.exe` and click **Install**.
2. Use the Start Menu / Desktop shortcut “Elite: Dangerous Colonization
   Assistant”.
3. Wait for the launcher to report “Ready” and click “Open Web UI”.

No additional tools (Python, Node, npm, Vite) are required on the user’s
machine; they are either embedded (Python via venv + bundled deps) or the
artifacts are pre-built (frontend `dist`).

---

## Bundling / distribution (high level)

It *is* possible to bundle the entire application as a local launchable program on Windows, Linux and macOS, but this requires OS‑specific build pipelines. At a high level:

### 1. Build the frontend

Produce a static bundle:

```bash
cd frontend
npm run build
```

This outputs static assets in `frontend/dist/` which can be:

- Served by FastAPI using `StaticFiles`, or
- Served by an external web server (NGINX, Apache, Caddy, etc).

A typical FastAPI mounting (example only) would live in [`backend/src/main.py`](backend/src/main.py:81):

```python
from fastapi.staticfiles import StaticFiles

app.mount(
    "/app",
    StaticFiles(directory="frontend/dist", html=True),
    name="frontend",
)
```

You can choose whether to expose the UI at `/` or under a path like `/app`.

### 2. Package backend + static frontend per OS

Regardless of OS, the bundle needs:

- Python runtime (if you don’t embed it).
- Backend code: [`backend/src/`](backend/src:1) and configs such as [`backend/config.yaml`](backend/config.yaml:1).
- Persistence: SQLite database created/used by [`ColonizationRepository`](backend/src/repositories/colonization_repository.py:64).
- Static frontend: `frontend/dist/`.

**Windows options (Python‑centric):**

- Use a “freezer” tool (one of):
  - PyInstaller
  - cx_Freeze
  - PyOxidizer
- Package the FastAPI app (plus `frontend/dist`) into:
  - A self‑contained executable, or
  - An installable directory with a launcher EXE.
- Entry point:
  - Run Uvicorn against `backend.src.main:app` (see [`backend/src/main.py`](backend/src/main.py:119)).
- Optional:
  - MSI / Inno Setup installer.
  - Start‑menu / desktop shortcuts that open the default browser at `http://localhost:8000` or the mounted frontend URL.

**Linux options:**

- Similar to Windows but per‑distro / per‑arch builds:
  - PyInstaller binary.
  - Native packages (`.deb`, `.rpm`) that:
    - Install Python runtime + dependencies.
    - Install `frontend/dist`.
    - Configure a systemd service that runs `uvicorn backend.src.main:app`.
- Optional:
  - A `.desktop` file to open the default browser pointing at the local URL.

**macOS options:**

- Use a bundler that can produce a `.app` bundle (e.g. Briefcase or PyInstaller with macOS support).
- Inside the `.app`:
  - Embed Python, backend code, config and `frontend/dist`.
  - Start the FastAPI/Uvicorn process on app launch.
  - Use `open http://localhost:8000` (or the chosen URL) to open the browser automatically.

### 3. All‑in‑one desktop app wrappers

If you prefer a single desktop window rather than “browser + local server”, you can wrap the existing HTTP/WebSocket API with:

- Electron
- Tauri
- Neutralino

In this model:

- The React UI runs inside the desktop shell.
- It communicates with the Python backend over:
  - `http://localhost:8000` and `ws://localhost:8000/ws/colonization`, or
  - Embedded Python bindings (more complex).

Pros:

- Single icon and window, feels more “native”.

Cons:

- Extra tooling complexity (build pipelines per platform).
- Larger runtime (especially with Electron).
- You still maintain the Python backend.

### Recommended path for this project

For this repository, a pragmatic evolution is:

1. **Short term** – keep using:
   - [`run-edca.bat`](run-edca.bat) on Windows.
   - [`run-edca.sh`](run-edca.sh) on Linux/macOS.
2. **Medium term** – serve `frontend/dist` from FastAPI and ship:
   - Per‑OS “frozen” backend binaries that embed the static frontend.
3. **Long term** – if desired, wrap the existing API in an Electron/Tauri shell for a single‑window experience.

---

## GameGlass integration

This project includes assets intended for GameGlass shard integration under:

- [`frontend/src/gameglass/`](frontend/src/gameglass:1)

For detailed API usage, endpoints, and layout guidance for shards, see:

- [`GameGlass-Integration.md`](GameGlass-Integration.md:1)

That document describes:

- How to call the backend APIs from a GameGlass-embedded web app.
- Which endpoints to use for system/site lists and aggregated commodity “shopping lists”.
- How to consume the WebSocket endpoint for live updates.