# Elite Dangerous Colonization Assistant

Elite Dangerous colonization support site and shard integration for GameGlass.

## Quick start (from project root)

All commands below are run from the project root directory (no `cd` into subfolders needed):

```bash
# Terminal 1 – backend (FastAPI)
uvicorn backend.src.main:app --reload
```

Backend will be available at:

- API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/colonization

```bash
# Terminal 2 – frontend (Vite + React)
npm --prefix frontend run dev
```

Frontend will be available at:
http://localhost:5173

> Note: The frontend is already configured to proxy API requests to `http://localhost:8000`, so make sure the backend is running before starting the frontend.

---

## Project layout

- Root project docs:
  - [`ARCHITECTURE.md`](ARCHITECTURE.md) – high-level system and component design
  - [`PROJECT_SETUP.md`](PROJECT_SETUP.md) – additional notes and setup details
- Backend (FastAPI, Python):
  - [`backend/README.md`](backend/README.md) – backend-specific commands, configuration, and troubleshooting
- Frontend (React + TypeScript):
  - [`frontend/README.md`](frontend/README.md) – frontend-specific commands, testing, and troubleshooting

## Backend overview

The backend is a FastAPI service that:

- Watches Elite: Dangerous journal logs
- Tracks the player’s current system
- Aggregates colonization/construction site data
- Exposes REST and WebSocket APIs for the frontend and GameGlass integration

Key config file:

- [`backend/config.yaml`](backend/config.yaml) – journal path, server host/port, CORS origins, logging, etc.

For detailed API endpoints, testing, and operational notes, see [`backend/README.md`](backend/README.md).

## Frontend overview

The frontend is a React + TypeScript single-page app (Vite) that:

- Lets you search and select star systems
- Displays construction sites and required commodities
- Uses color-coded progress and responsive layout
- Connects to the backend API (and WebSocket, where applicable)

See [`frontend/README.md`](frontend/README.md) for testing, build, and troubleshooting commands.

## GameGlass integration

This project includes assets intended for GameGlass shard integration under:

- [`frontend/src/gameglass/`](frontend/src/gameglass/)

Refer to [`GameGlass-Integration.md`](GameGlass-Integration.md) for details on how to use these with GameGlass.
