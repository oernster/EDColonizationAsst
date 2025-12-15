# Elite: Dangerous Colonization Assistant – Architecture

This document describes the current architecture of the Elite: Dangerous Colonization Assistant as implemented in this repository.

The system is split into:

- A Python **backend** that ingests Elite: Dangerous journal files, tracks colonization construction sites, and exposes REST+WebSocket APIs.
- A React/TypeScript **frontend** that visualizes system and site progress.
- Optional **GameGlass** integration assets.

---

## 1. System overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          React Frontend (Vite)                     │
│  - System selector, site list, settings UI                         │
│  - Talks to backend via:                                           │
│      • REST  → http://localhost:8000/api/*                         │
│      • WebSocket → ws://localhost:8000/ws/colonization             │
└─────────────────────────────────────────────────────────────────────┘
                            ▲                  ▲
                            │                  │
                   JSON over HTTP        JSON over WS
                            │                  │
                            ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Python Backend (FastAPI)                         │
│                                                                     │
│  FastAPI app: [`backend/src/main.py`](backend/src/main.py:1)        │
│                                                                     │
│  - Journal ingestion pipeline                                       │
│      • Watches Elite journals via watchdog                          │
│      • Parses relevant events                                       │
│      • Updates SQLite-backed repository                             │
│  - Aggregation services                                             │
│      • Aggregates data per system/site                              │
│      • Optionally enriches with Inara API data                      │
│  - APIs                                                             │
│      • REST routes under /api/*                                     │
│      • WebSocket endpoint /ws/colonization                          │
│                                                                     │
│  Persistence: [`backend/src/colonization.db`](backend/src/colonization.db) (*) │
│    (*) created at runtime by                                         │
│        [`ColonizationRepository`](backend/src/repositories/colonization_repository.py:64) │
└─────────────────────────────────────────────────────────────────────┘
                            ▲
                            │  filesystem (journal directory)
                            │
┌─────────────────────────────────────────────────────────────────────┐
│                 Elite: Dangerous Journal Files                      │
│  - Journal.*.log  (line-delimited JSON events)                     │
│  - Status.json (not currently parsed directly)                     │
│  Location (FSDJump, Docked, Location) events provide system/station│
│  Colonization* events provide construction depot state             │
└─────────────────────────────────────────────────────────────────────┘
```

The diagram above shows the logical data flow between the browser UI, the FastAPI backend, and Elite: Dangerous journal files.

In development, the React frontend typically runs on `http://localhost:5173` via Vite and talks to the FastAPI backend on `http://localhost:8000`.

In installer or "built runtime" mode, the React app is built into static assets under `frontend/dist` and served by the backend at `/app` using FastAPI `StaticFiles`. In that mode users normally access the UI via `http://127.0.0.1:8000/app/`.

In both modes, the backend exposes colonization REST and WebSocket APIs under `/api/*` and `/ws/colonization`, and additional Fleet carrier APIs under `/api/carriers/*` that reconstruct carrier state on demand from the latest journal file without using new database tables.

---

## 2. Backend architecture

### 2.1 Technology stack

- **Framework**: FastAPI + Uvicorn (`uvicorn backend.src.main:app`)
- **Language/runtime**: Python 3.10+
- **Config & settings**:
  - Pydantic v2 + `pydantic-settings` in [`backend/src/config.py`](backend/src/config.py:1)
  - YAML configuration in [`backend/config.yaml`](backend/config.yaml:1)
  - Commander/Inara secrets in `backend/commander.yaml` (user-created from example)
- **Persistence**: SQLite via `sqlite3` in [`ColonizationRepository`](backend/src/repositories/colonization_repository.py:64)
- **File watching**: `watchdog` in [`FileWatcher`](backend/src/services/file_watcher.py:326)
- **HTTP client**: `httpx` (for Inara integration) in [`backend/src/services/inara_service.py`](backend/src/services/inara_service.py:1)
- **WebSockets**: FastAPI WebSocket support in [`backend/src/api/websocket.py`](backend/src/api/websocket.py:1)
- **Logging**: Standard library logging configured in [`backend/src/utils/logger.py`](backend/src/utils/logger.py:1)
- **Tests**: `pytest` and friends under [`backend/tests/unit`](backend/tests/unit:1)

### 2.2 Project structure (backend)

```text
backend/
├── config.yaml                        # Main runtime configuration
├── example.commander.yaml             # Example per‑commander/Inara config
├── requirements.txt                   # Runtime dependencies
├── requirements-dev.txt               # Dev/test tooling
├── src/
│   ├── __init__.py                    # Package root, defines __version__
│   ├── main.py                        # FastAPI app, lifespan, entrypoint
│   ├── config.py                      # Pydantic settings and config loader
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                  # Core REST API under /api
│   │   ├── websocket.py               # /ws/colonization endpoint, broadcast
│   │   ├── settings.py                # /api/settings endpoints
│   │   ├── carriers.py                # /api/carriers endpoints (Fleet carriers)
│   │   └── journal.py                 # /api/journal/status, etc.
│   ├── models/
│   │   ├── __init__.py
│   │   ├── api_models.py              # Response models for REST
│   │   ├── colonization.py            # Core colonization domain models (sites, commodities)
│   │   ├── carriers.py                # Fleet carrier domain models
│   │   └── journal_events.py          # Typed journal event models
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── colonization_repository.py # SQLite-backed repository
│   ├── services/
│   │   ├── __init__.py
│   │   ├── journal_parser.py          # Parses Journal.*.log events
│   │   ├── file_watcher.py            # Watchdog integration and event pipeline
│   │   ├── data_aggregator.py         # Aggregates per-system data, Inara merge
│   │   ├── system_tracker.py          # Tracks current system/station
│   │   └── inara_service.py           # Thin wrapper around Inara API
│   └── utils/
│       ├── __init__.py
│       ├── journal.py                 # Journal-specific helpers
│       ├── logger.py                  # Logging configuration and helpers
│       └── windows.py                 # Windows-specific utilities (e.g. paths)
└── tests/
    ├── unit/                          # Unit and integration-style tests
    ├── fixtures/                      # Test data
    └── conftest.py                    # Shared pytest fixtures
```

### 2.3 Application lifecycle

The main FastAPI application is defined in [`backend/src/main.py`](backend/src/main.py:1).

Key points:

- A lifespan context manager (`lifespan`) is registered with the app to handle startup and shutdown.
- On startup, the following instances are created:

  - `ColonizationRepository` (SQLite) from [`colonization_repository.py`](backend/src/repositories/colonization_repository.py:64)
  - `DataAggregator` from [`data_aggregator.py`](backend/src/services/data_aggregator.py:36)
  - `SystemTracker` from [`system_tracker.py`](backend/src/services/system_tracker.py:1)
  - `JournalParser` from [`journal_parser.py`](backend/src/services/journal_parser.py:36)
  - `FileWatcher` from [`file_watcher.py`](backend/src/services/file_watcher.py:326)

- These instances are stored on `app.state` and also passed into:

  - `set_dependencies` in [`backend/src/api/routes.py`](backend/src/api/routes.py:32) so REST handlers can access the repository, aggregator and tracker.
  - `set_aggregator` in [`backend/src/api/websocket.py`](backend/src/api/websocket.py:1) so WebSocket broadcast handlers can query aggregated system data.

- The `FileWatcher`:

  - Uses configuration from [`backend/config.yaml`](backend/config.yaml:1) to locate the notebook/journal directory (`journal.directory`).
  - Starts a `watchdog.Observer` watching for `Journal.*.log` changes.
  - On startup, also runs an initial pass over all existing journal files to populate the repository.

- A callback (`notify_system_update` from [`websocket.py`](backend/src/api/websocket.py:1)) is registered via `file_watcher.set_update_callback(...)` so that when journal files change and system data is updated, connected WebSocket clients are notified.

- On shutdown, the lifespan handler stops the `FileWatcher` and its observer.

The root endpoint (`/`) in [`backend/src/main.py`](backend/src/main.py:108) returns static metadata including the current version and a link to `/docs` (FastAPI’s OpenAPI UI).

### 2.4 Configuration

Configuration is defined in [`backend/src/config.py`](backend/src/config.py:1) and loaded using `get_config()`.

Key config sources:

- **YAML** – [`backend/config.yaml`](backend/config.yaml:1)
  - Journal directory path.
  - Server host/port and allowed CORS origins.
  - WebSocket ping/reconnect behaviour.
  - Logging format and level.

- **Environment variables** (optionally) – used by `pydantic-settings` to override YAML values, typically for deployment scenarios.

Commander and Inara‑specific settings are stored separately:

- Example: [`backend/example.commander.yaml`](backend/example.commander.yaml:1)
- Actual: `backend/commander.yaml` (created by the user or written by the settings API / UI).

### 2.5 Data model overview

Core colonization-related models live in [`backend/src/models/colonization.py`](backend/src/models/colonization.py:1):

- **Commodity**
  - `name`, `name_localised`
  - `required_amount`, `provided_amount`
  - `payment`
  - Derived properties such as remaining amount and progress percentage.

- **ConstructionSite**
  - `market_id` (unique identifier per depot)
  - `station_name`, `station_type`
  - `system_name`, `system_address`
  - `construction_progress` (percentage)
  - `construction_complete` / `construction_failed`
  - `commodities: list[Commodity]`
  - `last_updated`

- **SystemColonizationData**
  - `system_name`
  - `construction_sites: list[ConstructionSite]`
  - `total_sites`, `completed_sites`, `in_progress_sites`
  - `completion_percentage` (derived)

- **CommodityAggregate**
  - Aggregated per‑commodity totals (required/provided/remaining) across all sites in a system.

API‑facing response models are defined in [`backend/src/models/api_models.py`](backend/src/models/api_models.py:1).

Typed journal event models (e.g. `ColonizationConstructionDepotEvent`, `ColonizationContributionEvent`, `LocationEvent`, `FSDJumpEvent`, `DockedEvent`, `CommanderEvent`) live in [`backend/src/models/journal_events.py`](backend/src/models/journal_events.py:1).

Fleet carrier models live in [`backend/src/models/carriers.py`](backend/src/models/carriers.py:1) and represent a derived view of carrier identity, cargo and buy/sell orders built directly from journal events such as `CarrierStats`, `CarrierLocation` and `CarrierTradeOrder`. These models are computed in memory when carrier endpoints are called and are not stored in the SQLite database.

### 2.6 Repository and persistence

[`ColonizationRepository`](backend/src/repositories/colonization_repository.py:64) is the central abstraction over persistent colonization data:

- Stores `ConstructionSite` records in SQLite (`construction_sites` table).
- Serializes `commodities` as JSON per row.
- Guards concurrent access with an `asyncio.Lock`:

  - Methods that modify or read multiple rows acquire the lock.
  - Care is taken to avoid deadlocks (e.g. `update_commodity` defers locking to operations it calls).

- Exposes asynchronous methods, including:

  - `add_construction_site(site)`
  - `get_site_by_market_id(market_id)`
  - `get_sites_by_system(system_name)`
  - `get_all_systems()`
  - `get_all_sites()`
  - `get_stats()` (total systems/sites, in‑progress vs completed)
  - `update_commodity(market_id, commodity_name, provided_amount)`
  - `clear_all()` (primarily for test and debug purposes)

### 2.7 Journal ingestion pipeline

The ingestion pipeline is implemented primarily in:

- [`backend/src/services/journal_parser.py`](backend/src/services/journal_parser.py:36)
- [`backend/src/services/file_watcher.py`](backend/src/services/file_watcher.py:326)
- [`backend/src/services/system_tracker.py`](backend/src/services/system_tracker.py:1)
- [`backend/src/repositories/colonization_repository.py`](backend/src/repositories/colonization_repository.py:64)

**Flow:**

1. The `FileWatcher` registers a `JournalFileHandler` with `watchdog.Observer` for the configured journal directory.
2. When `Journal.*.log` files are created or modified, the handler schedules asynchronous processing on the main event loop.
3. The `JournalParser`:

   - Reads each line in the journal file.
   - Parses JSON and filters to a set of **relevant** events:
     - `ColonizationConstructionDepot` / `ColonisationConstructionDepot`
     - `ColonizationContribution` / `ColonisationContribution`
     - `Location`
     - `FSDJump`
     - `Docked`
     - `Commander`
   - Creates strongly‑typed event instances defined in [`journal_events.py`](backend/src/models/journal_events.py:1).

4. For each event type:

   - `Location`, `FSDJump`, `Docked`:
     - Update the `SystemTracker`, which maintains the commander’s current system, station and docked status.
   - `Docked` at a colonization site:
     - Creates or updates a placeholder `ConstructionSite` with correct station and system metadata if needed.
   - `ColonizationConstructionDepot`:
     - Normalizes different journal payload styles (old `Commodities` vs new `ResourcesRequired`).
     - Merges with existing site metadata when present.
     - Updates or inserts a `ConstructionSite` in the repository.
   - `ColonizationContribution`:
     - Updates the corresponding `Commodity`’s `provided_amount` for the relevant site using `update_commodity`.

5. After processing a file, the handler collects the set of systems that changed and invokes the update callback (if configured). This callback is typically wired to WebSocket broadcasting so that connected clients receive live updates when:

   - Sites are discovered.
   - Commodity contributions change.
   - Construction sites complete.

The debug endpoint `/api/debug/reload-journals` in [`backend/src/api/routes.py`](backend/src/api/routes.py:199) uses the same parser/handler logic to rebuild state from scratch.

In contrast, Fleet carrier endpoints in [`backend/src/api/carriers.py`](backend/src/api/carriers.py:1) do not use the `FileWatcher` or repository at all. Instead they resolve the journal directory, locate the latest `Journal.*.log` file via helper functions in [`backend/src/utils/journal.py`](backend/src/utils/journal.py:1), parse that file on demand with `JournalParser.parse_file`, and then walk the resulting events in memory to infer carrier identity, cargo and trade orders.

### 2.8 Aggregation and Inara integration

[`DataAggregator`](backend/src/services/data_aggregator.py:36) is responsible for:

- Fetching all sites in a given system from the repository.
- Optionally fetching additional colonization data from Inara via [`InaraService`](backend/src/services/inara_service.py:1).
- Combining local (journal‑derived) and remote (Inara) information according to the following rules:

  - Local, incomplete sites remain driven by journal data.
  - Inara can **upgrade** local sites to completed if Inara reports them as complete.
  - Inara can add completed sites that do not exist locally.
  - Inara data is never allowed to downgrade or create “phantom” incomplete sites that the commander has never seen.

- Providing:

  - `aggregate_by_system(system_name) → SystemColonizationData`
  - `aggregate_commodities(sites) → list[CommodityAggregate]`
  - `get_system_summary(system_name)` – convenience summary (counts, most‑needed commodity etc.)

This aggregation logic underpins:

- `/api/system`
- `/api/system/commodities`
- `/api/sites` (which walks all systems and uses aggregated views).

### 2.9 REST API

Core REST routes are implemented in [`backend/src/api/routes.py`](backend/src/api/routes.py:1) and use the repository, aggregator and system tracker injected via `set_dependencies`.

Key endpoints:

- **Health and meta**

  - `GET /api/health` – basic health check and journal directory accessibility.

- **Systems and sites**

  - `GET /api/systems` – list of all systems that have at least one construction site.
  - `GET /api/systems/search?q=...` – simple case‑insensitive substring search over known systems (for autocomplete).
  - `GET /api/systems/current` – current system/station and docked status from `SystemTracker`.
  - `GET /api/system?name=...` – full `SystemColonizationData` view for a system.
  - `GET /api/system/commodities?name=...` – aggregated per‑commodity “shopping list” for a system.
  - `GET /api/sites` – global view of all sites, split into in‑progress vs completed.
  - `GET /api/sites/{market_id}` – details for a single `ConstructionSite`.
  - `GET /api/stats` – high‑level stats from the repository.

- **Debug**

  - `POST /api/debug/reload-journals` – clears repository state and reprocesses all journal files using the same pipeline as the live watcher.

- **Fleet carriers** (journal‑derived, no additional DB tables)

  - `GET /api/carriers/current` – returns whether the commander is currently docked at a fleet carrier and, if so, a `CarrierIdentity` reconstructed from the latest relevant `Docked`, `CarrierStats` and `CarrierLocation` events.
  - `GET /api/carriers/current/state` – returns a full `CarrierState` snapshot (identity, inferred cargo, buy/sell orders and cargo/capacity metrics) for the carrier the commander is currently docked at.
  - `GET /api/carriers/mine` – returns a list of carriers owned by the commander (and, in future, squadron carriers) based primarily on `CarrierStats` and `CarrierLocation` events.

Additional routers:

- [`backend/src/api/settings.py`](backend/src/api/settings.py:1)
  - `GET /api/settings` and `POST /api/settings` to read/update config (including Inara settings and journal directory).
- [`backend/src/api/journal.py`](backend/src/api/journal.py:1)
  - `GET /api/journal/status` for a minimal, journaling‑oriented status view.

### 2.10 WebSocket endpoint

The WebSocket endpoint is implemented in [`backend/src/api/websocket.py`](backend/src/api/websocket.py:1) and mounted at:

- `WS /ws/colonization`

Responsibilities:

- Maintain active WebSocket client connections.
- Support simple message types, such as:

  - Subscribe/unsubscribe to specific systems.
  - Receive `update` messages when a subscribed system’s data changes (via the file watcher callback).

Under the hood, `websocket.py` uses the `DataAggregator` to fetch up‑to‑date `SystemColonizationData` for systems whenever journal events lead to repository changes.

---

## 3. Frontend architecture

### 3.1 Technology stack

- **Framework**: React 18 with TypeScript
- **State management**: Zustand
- **UI components**: Material‑UI (MUI)
- **HTTP client**: Axios
- **Build tool / dev server**: Vite
- **Testing**: Vitest + Testing Library

### 3.2 Project structure (frontend)

```text
frontend/
├── index.html                    # Root HTML template
├── package.json                  # NPM scripts and dependencies
├── tsconfig.json                 # TypeScript config
├── vite.config.ts                # Vite config (incl. dev proxy to backend)
└── src/
    ├── main.tsx                  # React entry point
    ├── App.tsx                   # Top‑level app component
    ├── index.css                 # Global styles
    ├── components/
    │   ├── SystemSelector/
    │   │   └── SystemSelector.tsx
    │   ├── SiteList/
    │   │   └── SiteList.tsx
    │   ├── FleetCarriers/
    │   │   └── FleetCarriersPanel.tsx
    │   └── Settings/
    │       └── SettingsPage.tsx
    ├── services/
    │   └── api.ts                # Axios client and typed API helpers
    ├── stores/
    │   ├── colonizationStore.ts  # Zustand store for colonization data
    │   └── carrierStore.ts       # Zustand store for Fleet carrier data
    ├── types/
    │   ├── colonization.ts       # Shared frontend types for colonization data
    │   ├── fleetCarriers.ts      # Types for Fleet carrier data
    │   └── settings.ts           # Types for settings/inara config
    ├── gameglass/
    │   ├── app.js
    │   ├── index.html
    │   └── style.css
    └── test/
        └── setup.ts              # Vitest + Testing Library setup
```

### 3.3 Data flow

- The frontend obtains **initial data** via REST:

  - `/api/systems` to populate the system selector.
  - `/api/system` and `/api/system/commodities` to show system‑level and aggregated commodity views.
  - `/api/journal/status` and `/api/settings` for status/settings screens.

- For **live updates**, it connects to `ws://localhost:8000/ws/colonization`:

  - Subscribes to one or more systems.
  - Receives update messages whenever the backend’s file watcher processes new journal events and notifies the WebSocket layer.

- Colonization state is centralized in the `colonizationStore` in [`frontend/src/stores/colonizationStore.ts`](frontend/src/stores/colonizationStore.ts:1):

  - Stores the current system selection, latest `SystemColonizationData` for that system, commodity aggregates, loading/error states, etc.
  - Exposes actions to update system selection, handle incoming WebSocket messages, and refresh REST data.

- Fleet carrier state is managed separately in the `carrierStore` in [`frontend/src/stores/carrierStore.ts`](frontend/src/stores/carrierStore.ts:27):

  - Loads the current docked carrier identity and state via `/api/carriers/current` and `/api/carriers/current/state`.
  - Loads the commander's own carriers via `/api/carriers/mine`.
  - Exposes loading and error flags used by the Fleet carriers UI.

### 3.4 Key components (frontend)

- **SystemSelector** – [`frontend/src/components/SystemSelector/SystemSelector.tsx`](frontend/src/components/SystemSelector/SystemSelector.tsx:1)

  - Renders a dropdown/autocomplete of known systems.
  - Uses `/api/systems` and `/api/systems/search` for options.
  - Updates the selected system in the store and triggers data fetch/subscription.

- **SiteList** – [`frontend/src/components/SiteList/SiteList.tsx`](frontend/src/components/SiteList/SiteList.tsx:1)

  - Displays construction sites for the currently selected system.
  - Groups by in‑progress vs completed.
  - Shows commodity requirements and per‑site completion.

- **FleetCarriersPanel** – [`frontend/src/components/FleetCarriers/FleetCarriersPanel.tsx`](frontend/src/components/FleetCarriers/FleetCarriersPanel.tsx:1)

  - Renders the Fleet carriers tab under the System View.
  - Shows the currently docked carrier (if any), including identity, services, cargo snapshot and market orders derived from journal data.
  - Lists the commander's known carriers based on `CarrierStats`/`CarrierLocation` journal events.

- **SettingsPage** – [`frontend/src/components/Settings/SettingsPage.tsx`](frontend/src/components/Settings/SettingsPage.tsx:1)

  - Manages journal directory and Inara/commander settings through `/api/settings`.
  - Writes changes back to the backend (which in turn persists to YAML).

- **App / main** – [`frontend/src/App.tsx`](frontend/src/App.tsx:1), [`frontend/src/main.tsx`](frontend/src/main.tsx:1)

  - Compose the layout, routes (if any) and top‑level state providers.
  - Wire WebSocket connection and REST fetches into the store.

---

## 4. Journal, settings and commander/Inara configuration

### 4.1 Journal configuration

The backend reads its journal directory from config:

- [`backend/config.yaml`](backend/config.yaml:1) → `journal.directory`
- Overrideable via environment variables via [`backend/src/config.py`](backend/src/config.py:1)

The journal directory typically points to:

```text
C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous
```

### 4.2 Commander and Inara configuration

Per‑commander settings live in a YAML file:

- Example template: [`backend/example.commander.yaml`](backend/example.commander.yaml:1)
- Runtime file: `backend/commander.yaml` (ignored by Git; created/updated by the settings UI or manually)

The Inara service in [`backend/src/services/inara_service.py`](backend/src/services/inara_service.py:1) reads this configuration to:

- Obtain API key and commander name.
- Call Inara’s API to fetch colonization site status and progress.
- Provide structured data to `DataAggregator` for merging with local journal data.

---

## 5. GameGlass integration

GameGlass‑specific assets are in:

- [`frontend/src/gameglass`](frontend/src/gameglass:1)

and are documented in detail in:

- [`GameGlass-Integration.md`](GameGlass-Integration.md:1)

These assets and docs cover:

- How GameGlass shards can call the backend APIs.
- Which endpoints to use for system lists, per‑site data and aggregated commodities.
- How to use the WebSocket endpoint for live updates inside a GameGlass‑hosted web view.

---

## 6. Deployment and local usage

### 6.1 Local development / usage

For non‑developers, the primary entrypoints are:

- Windows: the installed application started from the Start Menu (backed by a packaged backend executable) or the helper script [`run-edca.bat`](run-edca.bat:1) from a source checkout.
- Linux: distro‑specific helper scripts such as [`run-edca-built-debian.sh`](run-edca-built-debian.sh:1), [`run-edca-built-fedora.sh`](run-edca-built-fedora.sh:1), [`run-edca-built-arch.sh`](run-edca-built-arch.sh:1), [`run-edca-built-rhel.sh`](run-edca-built-rhel.sh:1) and [`run-edca-built-void.sh`](run-edca-built-void.sh:1) from the project root.

These packaged or "built runtime" entrypoints:

- Ensure the backend runtime environment is available.
- Serve the built frontend from `frontend/dist` at the `/app` mount point configured in [`backend/src/main.py`](backend/src/main.py:144).
- Start the backend on `http://127.0.0.1:8000` and open the browser at `http://127.0.0.1:8000/app/`.

For development from a source checkout, you can also run backend and frontend separately:

- Backend from the project root:

  ```bash
  uvicorn backend.src.main:app --reload
  ```

- Frontend from the project root:

  ```bash
  npm --prefix frontend run dev
  ```

or follow the more detailed workflows in [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1).

### 6.2 Towards bundling / packaging

High‑level packaging options (also sketched in [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1)) include:

Current Windows installer builds and Linux helper scripts already implement a variant of this shape, where the bundled backend serves the built React frontend from `/app` via FastAPI `StaticFiles`.

- Building the frontend into static assets (`npm run build` → `frontend/dist`).
- Serving those assets via FastAPI `StaticFiles`, potentially at `/` or `/app`.
- Freezing the backend + static frontend into:

  - Windows: PyInstaller / cx_Freeze / PyOxidizer bundles.
  - Linux: per‑distro packages or self‑contained binaries.
  - macOS: `.app` bundles via Briefcase/PyInstaller.

The live architecture (journal watcher → repository → aggregator → REST/WS → React UI) stays the same; only the deployment shape changes.

---

## 7. Testing and quality

### 7.1 Backend

Backend tests live under [`backend/tests/unit`](backend/tests/unit:1) and include coverage of:

- Journal parsing (`test_journal_parser.py`)
- File watching and event handling (`test_file_watcher.py`)
- Data aggregation (`test_data_aggregator.py`)
- System tracking and utility functions (`test_system_tracker_and_utils.py`)
- API routes (`test_api_routes.py`, `test_api_journal_and_settings.py`, `test_api_carriers.py`)
- WebSocket behaviour (`test_websocket.py`)
- Repository persistence (`test_repository.py`)
- Main app wiring (`test_main_app.py`)
- Domain models (`test_models.py`)

Quality tooling:

- Type checking via `mypy` (configured in [`backend/mypy.ini`](backend/mypy.ini:1))
- Formatting via `black` and `isort`
- Linting via `pylint` (see [`backend/requirements-dev.txt`](backend/requirements-dev.txt:1))

### 7.2 Frontend

Frontend tests and setup live under:

- [`frontend/src/App.test.tsx`](frontend/src/App.test.tsx:1)
- [`frontend/src/test/setup.ts`](frontend/src/test/setup.ts:1)

The stack uses:

- Vitest for running tests.
- React Testing Library for DOM interaction.
- TypeScript’s compiler for type checking.

Linting and type checks can be run via the NPM scripts in [`frontend/package.json`](frontend/package.json:1).

---

## 8. Future enhancements

The current architecture is designed to be:

- **Extensible** – new event types, aggregation strategies and views can be added without disrupting existing layers.
- **Testable** – key components are covered by unit and integration‑style tests.
- **Deployable** – supports lightweight local use and can be evolved towards per‑OS packaged binaries or wrapped desktop apps (e.g. Electron/Tauri) as needed.

Potential future directions include:

- Richer analytics and history (e.g. long‑term storage of progress over time).
- Smarter trade‑route suggestions based on required commodities.
- Multi‑commander support and squadron sharing.
- Tighter integration between GameGlass shards and the React UI.

This document reflects the current code layout and behaviour of the backend and frontend in this repository. For detailed implementation specifics, consult the linked modules and tests throughout this file.