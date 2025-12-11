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

