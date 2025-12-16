# Elite: Dangerous Colonization Assistant – Architecture Overview

This document is the **front door** to the EDCA architecture. It gives you the big picture and points you to the detailed backend and frontend/runtime documents that now serve as the source of truth.

---

## 1. High‑level system overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          React Frontend (Vite)                     │
│  - System selector, site list, Fleet Carriers, settings UI         │
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
│  - Journal ingestion pipeline                                       │
│      • Watches Elite journals via watchdog                          │
│      • Parses relevant events                                       │
│      • Updates SQLite-backed repository                             │
│  - Aggregation services                                             │
│      • Aggregates data per system/site                              │
│      • Optionally enriches with Inara data                          │
│  - APIs                                                             │
│      • REST routes under /api/*                                     │
│      • WebSocket endpoint /ws/colonization                          │
│      • Fleet carrier endpoints under /api/carriers/*                │
└─────────────────────────────────────────────────────────────────────┘
                            ▲
                            │  filesystem (journal directory)
                            │
┌─────────────────────────────────────────────────────────────────────┐
│                 Elite: Dangerous Journal Files                      │
│  - Journal.*.log  (line-delimited JSON events)                      │
│  - Location/FSDJump/Docked/Commander events track context           │
│  - Colonisation* events expose construction depot state             │
│  - Carrier* events expose Fleet carrier state                       │
└─────────────────────────────────────────────────────────────────────┘
```

At a glance:

- The **backend** watches and parses Elite: Dangerous journal files, persists colonisation state in SQLite, reconstructs Fleet carrier state in memory, and exposes REST/WebSocket APIs.
- The **frontend** is a React/TypeScript app (MUI, Zustand, Vite) that consumes those APIs to show system progress, shopping lists, carrier state, and settings.
- A **runtime layer** (Qt launcher, tray, packaged EXE) wraps the backend and serves the built frontend to end users, enforcing a single‑instance guarantee per OS user.

---

## 2. Detailed architecture documents

For implementation‑level detail, use the split architecture docs at the project root:

### 2.1 Backend architecture

See [`ARCHITECTURE_1_backend.md`](ARCHITECTURE_1_backend.md:1).

That document focuses on:

- FastAPI app structure and lifespan.
- Journal ingestion:
  - Parser, file watcher, system tracker.
  - First‑run import vs incremental updates.
- Colonisation data model and SQLite repository:
  - `ConstructionSite`, `Commodity`, `SystemColonizationData`, `CommodityAggregate`.
  - DB schema, versioning and automatic reset for incompatible schema changes.
- Fleet carrier state reconstruction from carrier journal events:
  - `CarrierLocation`, `CarrierStats`, `CarrierTradeOrder`.
  - Normalisation of commodity identifiers and display names.
- Data aggregation and optional Inara integration.
- Backend REST and WebSocket APIs.
- Backend testing and quality tooling.

### 2.2 Frontend & runtime architecture

See [`ARCHITECTURE_2_frontend_and_runtime.md`](ARCHITECTURE_2_frontend_and_runtime.md:1).

That document focuses on:

- React/TypeScript frontend:
  - Component structure (SystemSelector, SiteList, FleetCarriersPanel, SettingsPage).
  - Stores (`colonizationStore`, `carrierStore`) and hooks (`useColonizationWebSocket`).
  - How the UI uses `/api/*` and `/ws/colonization`.
- Fleet Carriers UI:
  - Current docked carrier header and services.
  - Cargo and buy/sell order presentation.
  - Known own/squadron carriers list.
- Settings UI:
  - Journal directory configuration.
  - Commander/Inara settings (with Inara integration currently dormant).
- Runtime / launcher / tray stack:
  - `ApplicationInstanceLock` and single‑instance behaviour.
  - Dev launcher window and tray controller.
  - Packaged/frozen runtime (in‑process uvicorn + Qt tray).
- Deployment and helper scripts for running EDCA on different platforms.
- Frontend and runtime tests.

These two files are the authoritative, up‑to‑date references for how EDCA works internally.

---

## 3. Other useful documentation

- **Development workflows and tooling**  
  [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1)  
  - How to run backend and frontend in development.
  - Test/lint/type‑checking commands.
  - Packaging and installer notes.

- **GameGlass integration**  
  [`GameGlass-Integration.md`](GameGlass-Integration.md:1)  
  - How to use EDCA’s APIs and WebSocket endpoint from GameGlass shards.
  - Which endpoints to call for system lists, site data, and aggregated commodities.

- **Project setup**  
  [`PROJECT_SETUP.md`](PROJECT_SETUP.md:1)  
  - Environment prerequisites.
  - Initial setup steps for contributors.

- **Top‑level README**  
  [`README.md`](README.md:1)  
  - What EDCA is, how to install and run it as an end user.
  - Links to the architecture docs and development notes.

---

## 4. Suggested reading order

For a new contributor (or a future you coming back to the project):

1. Start here, in this overview, to understand the major moving parts.
2. Read:
   - [`ARCHITECTURE_1_backend.md`](ARCHITECTURE_1_backend.md:1) if you are working on parsing, ingestion, APIs, or persistence.
   - [`ARCHITECTURE_2_frontend_and_runtime.md`](ARCHITECTURE_2_frontend_and_runtime.md:1) if you are working on the React UI, Fleet Carriers panel, or the Qt/runtime stack.
3. Use the inline file/line links in those docs to jump directly to concrete implementations and tests.

This keeps `ARCHITECTURE.md` small and navigational, while the split backend/frontend documents carry the full architectural detail.