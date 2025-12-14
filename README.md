# Elite Dangerous Colonization Assistant

Elite Dangerous Colonization Assistant (EDCA) helps you track in‑game colonization efforts and related construction sites through a local web UI.

---

## Get the app on Windows

For normal Windows use, download the prebuilt installer (no Python or Node.js required):

1. Go to the project’s **GitHub Releases** page.
2. Download the latest Windows installer executable, typically named:

   ```text
   EDColonizationAsstInstaller.exe
   ```

3. Double‑click it and follow the on‑screen instructions (Install / Repair / Uninstall).
4. After installation, launch **Elite: Dangerous Colonization Assistant** from the
   Start Menu or Desktop shortcut.

> **Note:** Because this is not a code‑signed commercial product, Windows SmartScreen
> (and some antivirus tools) may warn that the installer or runtime is from an
> unrecognised publisher. If you are unsure, you can always review the complete
> source code in this repository to reassure yourself before choosing to run the
> installer.

The installed runtime starts a local web server and opens your browser to:

```text
http://127.0.0.1:8000/app/
```

---

## Access from a tablet or phone on the same network

You can open the EDCA UI from another device (for example, a tablet) as long as:

- The PC running EDCA and the tablet/phone are on the **same local network** (Wi‑Fi/LAN).
- Your firewall allows local access to port `8000` on the PC.

### 1. Find your PC’s LAN IP address (Windows)

On the Windows PC where EDCA is installed:

1. Press `Win + R`, type `cmd` and press Enter to open Command Prompt, or open PowerShell.
2. Run:

   ```text
   ipconfig
   ```

3. Find your active network adapter (for example `Wi‑Fi` or `Ethernet`).
4. Under that adapter, look for the line:

   ```text
   IPv4 Address . . . . . . . . . . : 192.168.1.238
   ```

   The `192.168.x.x` (or `10.x.x.x`) value is your **LAN IP**.

### 2. Use that IP on your tablet/phone (local network only)

On your tablet/phone (connected to the same Wi‑Fi/LAN):

1. Open a browser (Chrome, Edge, Safari, etc.).
2. Enter the following URL, replacing `<PC-LAN-IP>` with the IPv4 address you found:

   ```text
   http://<PC-LAN-IP>:8000/app/
   ```

   Example:

   ```text
   http://192.168.1.238:8000/app/
   ```

This works **only on your local network**; EDCA is not intended to be exposed directly to the internet.

---

## Development / source checkout

If you have cloned the repository and want to build or run EDCA from source (backend/frontend dev, tests, installer builds), see:

- [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:1)
