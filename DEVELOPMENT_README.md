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

Key config files:

- [`backend/config.yaml`](backend/config.yaml:1) – journal path, server host/port, CORS origins, logging, etc.
- [`backend/commander.yaml`](backend/commander.yaml:1) – local commander / Inara credentials (API key, commander name, optional app name). This file is **not** tracked by git (see [`.gitignore`](.gitignore:209)).

### Commander / Inara configuration

Commander-specific and Inara secrets live in [`backend/commander.yaml`](backend/commander.yaml:1). Example:

```yaml
inara:
  app_name: "ED Colonization Assistant"
  api_key: "INARA-API-KEY-GOES-HERE"
  commander_name: "CMDR Example"
```

Notes:

- Do **not** commit your real API key or commander name; `backend/commander.yaml` is already ignored via [`.gitignore`](.gitignore:209).
- You can populate this file in two ways:
  - Via the **Settings** page in the UI (Inara API Key + Commander Name fields), which will write/update `backend/commander.yaml` for you.
  - By creating/editing `backend/commander.yaml` manually using the structure above.

For detailed API endpoints, testing, and operational notes, see [`backend/README.md`](backend/README.md:1).

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