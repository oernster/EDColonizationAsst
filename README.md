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

The backend may need your Inara credentials in order to enrich colonization data for your commander in future; to add those...

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

---

## Accessing the UI from another device (tablet / phone)

You can access the frontend from another device on your network (for example, a tablet) using your PC’s LAN IP address and port **5173**.

### 1. Ensure Vite is listening on all interfaces

This is already configured in [`frontend/vite.config.ts`](frontend/vite.config.ts:13):

- `host: '0.0.0.0'`
- `port: 5173`

Start the frontend as usual from the project root:

```bash
npm --prefix frontend run dev
```

Vite will print something like:

```text
VITE v5.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.1.238:5173/
  ➜  Network: http://100.120.202.64:5173/
  ➜  Network: http://172.29.128.1:5173/
  ➜  Network: http://169.254.237.11:5173/
```

The **Local** URL is for your PC. The **Network** URLs correspond to each active network interface. Typically the one you want for home LAN use is the `192.168.x.x` (or `10.x.x.x`) address.

### 2. Find your LAN IP address (Windows)

On Windows, you can find the LAN IP in several ways:

**Option A – Use the Vite output**

- When you run `npm --prefix frontend run dev`, look for the `Network:` lines.
- Use the address that looks like a home LAN IP, e.g.:

  ```text
  http://192.168.1.238:5173/
  ```

**Option B – Use `ipconfig`**

1. Open PowerShell or Command Prompt.
2. Run:

   ```bash
   ipconfig
   ```

3. Look for the adapter that corresponds to your active network (e.g. `Wi‑Fi` or `Ethernet`), not virtual adapters (VPN, Docker, Hyper‑V).
4. Under that adapter, find the line:

   ```text
   IPv4 Address . . . . . . . . . . : 192.168.1.238
   ```

5. Use that IP with port 5173 in your tablet’s browser:

   ```text
   http://192.168.1.238:5173
   ```

### 3. Find your LAN IP address (Linux)

On Linux, you can use one of:

**Option A – `ip addr`**

```bash
ip addr
```

- Look for your primary interface (often `eth0`, `enpXsY`, or `wlpXsY`).
- Find the `inet` line, e.g.:

  ```text
  inet 192.168.1.238/24 brd 192.168.1.255 scope global dynamic
  ```

- Use the `192.168.1.238` part with port 5173:

  ```text
  http://192.168.1.238:5173
  ```

**Option B – `hostname -I`**

```bash
hostname -I
```

This prints one or more IP addresses. Pick the one in your home LAN range (typically `192.168.x.x` or `10.x.x.x`), not:

- `127.0.0.1` (loopback),
- `169.254.x.x` (link‑local),
- or addresses used by containers/VPNs unless that’s specifically what you want.

### 4. Connect from your tablet / phone

1. Make sure:
   - The backend is running (default `http://localhost:8000` on the PC).
   - The frontend dev server is running on your PC on port 5173.
   - Your tablet/phone is on the **same Wi‑Fi / LAN** as the PC.
   - Your PC’s firewall allows inbound connections on port 5173 (and 8000 if you access the backend directly).

2. On your tablet/phone, open Chrome (or another browser) and enter:

   ```text
   http://<PC-LAN-IP>:5173
   ```

   For example:

   ```text
   http://192.168.1.238:5173
   ```

You can ignore extra “Network” URLs that Vite prints (e.g. `100.x.x.x`, `172.x.x.x`, `169.254.x.x`) unless you specifically know you are connecting via VPN/Docker/etc. For typical home setups, use the `192.168.x.x:5173` (or `10.x.x.x:5173`) address.

