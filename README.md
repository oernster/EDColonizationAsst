# Elite Dangerous Colonization Assistant

Elite Dangerous Colonization Assistant (EDCA) helps you track in‑game colonization efforts and related construction sites through a local web UI.

<img width="1582" height="1248" alt="{D494D007-E38F-465D-9AF5-BF34A431AEF3}" src="https://github.com/user-attachments/assets/9b73bf79-8524-4c58-bd9e-ae8e70fc08ec" />
<img width="1581" height="1180" alt="{173686A9-ADF6-4BC7-A637-A72F629DFEF4}" src="https://github.com/user-attachments/assets/e52917a0-dc5f-4938-b708-5151eb1f7060" />

---

### If you like it please buy me a coffee: [Donation link](https://www.paypal.com/ncp/payment/Z36XJEEA4MNV6)

## Fleet carrier data and journal updates

EDCA's Fleet Carrier view (cargo and market orders) is built **entirely** from the official Elite Dangerous journal files. The game only writes carrier trade information to the journals when you **edit or refresh trade orders on your carrier** (for example, by changing or cancelling a buy/sell order in the Carrier Management screen).

This has two important consequences:

- If you change your carrier's market in‑game but the game does **not** emit new journal events (such as `CarrierTradeOrder` entries), EDCA cannot see that change and the UI will continue to show the last state that was recorded in the journals.
- To ensure EDCA shows valid, up‑to‑date carrier commodity data, you may occasionally need to:
  - Open the Carrier Management screen and adjust or re‑apply your commodity orders (even if only by toggling/cancelling and re‑creating them), so that the game writes fresh carrier trade events to the journal.
  - Wait a moment for the journal watcher to ingest the new lines and for the UI to refresh.

EDCA cannot force Elite Dangerous to write new journal data; it can only reflect what is actually present in your local `Journal.*.log` files.

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

## Run on Linux

If you are running EDCA from a local checkout on Linux, use the distro-specific helper script from the project root:

- Debian / Ubuntu / Linux Mint: [`./run-edca-built-debian.sh`](run-edca-built-debian.sh:1) (recommended)
- Fedora: [`./run-edca-built-fedora.sh`](run-edca-built-fedora.sh:1) (**UNTESTED** helper)
- Arch Linux: [`./run-edca-built-arch.sh`](run-edca-built-arch.sh:1) (**UNTESTED** helper)
- RHEL / Rocky / Alma: [`./run-edca-built-rhel.sh`](run-edca-built-rhel.sh:1) (**UNTESTED** helper)
- Void: [`./run-edca-built-void.sh`](run-edca-built-void.sh:1) (**UNTESTED** helper)

Each script:

- Sets up a Python virtual environment and backend runtime dependencies.
- Ensures the frontend is built (or lets you skip the build via environment variables).
- Starts the backend on `http://127.0.0.1:8000`.
- Opens your browser at `http://127.0.0.1:8000/app/`.

For full Linux prerequisites and advanced usage (including environment variables and alternative workflows), see [`DEVELOPMENT_README.md`](DEVELOPMENT_README.md:666).

The installed runtime starts a local web server and opens your browser to:

```text
http://127.0.0.1:8000/app/
```

---

## Elite Dangerous journal log location

EDCA reads **Elite Dangerous journal files** directly from your local save folder. On a default Windows installation of the game (non‑Horizons4), the journals are typically located at:

```text
C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous
```

If you run Elite via Steam Proton or Wine on Linux, the journal directory is usually under your Proton/Wine prefix, for example:

```text
~/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
```

You can point EDCA at a different journal directory via the Settings page in the web UI (`Journal directory` field). The backend will monitor whatever path is configured there for `Journal.*.log` files.

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
