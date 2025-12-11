# Elite Dangerous Colonization Assistant

Elite Dangerous colonization support site and shard integration for GameGlass.

## Quick start (from project root)

All commands below are run from the project root directory (no `cd` into subfolders needed):

```bash
# Terminal 1 – backend (FastAPI)
uvicorn backend.src.main:app
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

## Commander / Inara configuration

The backend needs your Inara credentials in order to enrich colonization data for your commander.

Configuration is stored in a YAML file in the `backend` directory:

- Example template: `backend/example.commander.yaml`
- Runtime config file: `backend/commander.yaml` (this is what the app actually reads)

To configure:

1. Copy the example file:

   ```bash
   cp backend/example.commander.yaml backend/commander.yaml
   ```

2. Edit `backend/commander.yaml` and set:

   - `inara.api_key` – your personal Inara API key.
   - `inara.commander_name` – the exact commander name associated with that key.
   - (Optional) `inara.app_name` – your registered Inara application name, if you have one.

3. Start (or restart) the backend as shown above. The configuration loader will read `backend/commander.yaml` and use those values.

You can also adjust these values through the web UI’s settings page, which will write back into `backend/commander.yaml`.

