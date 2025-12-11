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

1. **Create virtual environment:**

   ```bash
   python -m venv venv
   ```

2. **Activate virtual environment:**

   ```bash
   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements-dev.txt
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

From the **`backend/` directory**:

#### Run all tests

```bash
pytest
```

#### Run with coverage

```bash
pytest --cov=src --cov-report=html
```

#### Run specific test file

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
  - Run `pip install -r requirements-dev.txt` from the `backend/` directory.

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

## GameGlass integration

This project includes assets intended for GameGlass shard integration under:

- [`frontend/src/gameglass/`](frontend/src/gameglass:1)

For detailed API usage, endpoints, and layout guidance for shards, see:

- [`GameGlass-Integration.md`](GameGlass-Integration.md:1)

That document describes:

- How to call the backend APIs from a GameGlass-embedded web app.
- Which endpoints to use for system/site lists and aggregated commodity “shopping lists”.
- How to consume the WebSocket endpoint for live updates.