from __future__ import annotations

"""
Runtime entrypoint for the Elite: Dangerous Colonization Assistant.

This module is designed to be used as the main entry when building a
self-contained runtime executable with Nuitka. It supports two modes:

- Development mode (DEV):
  Launched via the regular Python interpreter. Behaviour is delegated to
  the existing launcher window and virtual-environment logic so that the
  developer experience remains unchanged.

- Frozen mode (FROZEN):
  Launched via a Nuitka-built EXE that embeds Python and all backend
  dependencies. In this mode we:
    * Start the FastAPI backend (uvicorn) in-process.
    * Provide a simple Qt tray UI with an "Open Web UI" and "Exit" action.
    * Do NOT rely on any system-wide Python installation.

The actual EXE build step will target this module, e.g.:

    python -m nuitka --onefile --enable-plugin=pyside6 backend/src/runtime_entry.py

The runtime mode detection is encapsulated in
[`backend.src.utils.runtime`](backend/src/utils/runtime.py:1).
"""

import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .main import app as fastapi_app
from .utils.logger import get_logger, setup_logging
from .utils.runtime import RuntimeMode, get_runtime_mode

# --------------------------------------------------------------------------- logging

setup_logging()
logger = get_logger(__name__)


# --------------------------------------------------------------------------- environment


@dataclass(frozen=True)
class RuntimeEnvironment:
    """
    Represents the runtime environment for the application.

    This encapsulates derived paths and constants that are shared by the
    backend server controller and the tray UI.
    """

    mode: RuntimeMode
    project_root: Path
    backend_port: int = 8000

    @property
    def frontend_url(self) -> str:
        """Return the URL of the web UI served by the backend."""
        return f"http://127.0.0.1:{self.backend_port}/app/"

    @property
    def icon_path(self) -> Path:
        return self.project_root / "EDColonizationAsst.ico"

    @classmethod
    def detect(cls) -> "RuntimeEnvironment":
        mode = get_runtime_mode()
        # backend/src/runtime_entry.py -> src -> backend -> project_root
        project_root = Path(__file__).resolve().parents[2]
        return cls(mode=mode, project_root=project_root)


# --------------------------------------------------------------------------- backend server controller


class BackendServerController:
    """
    Controls the FastAPI backend server.

    In FROZEN mode we start an in-process uvicorn.Server in a background
    thread so that no external Python interpreter is required. In DEV mode
    we currently do not use this controller; instead the existing launcher
    behaviour is preserved. The DEV hooks are provided for future extension.
    """

    def __init__(self, env: RuntimeEnvironment) -> None:
        self._env = env
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------- public API -----------------------------

    def start(self) -> None:
        """Start the backend server appropriate for the current runtime mode."""
        if self._env.mode is RuntimeMode.FROZEN:
            self._start_inprocess()
        else:
            # For now DEV mode is handled by the existing launcher; we leave
            # this hook in place for possible future use.
            logger.info("BackendServerController.start() called in DEV mode; "
                        "no-op (launcher handles backend in development).")

    def stop(self) -> None:
        """Stop the backend server if it was started in-process."""
        if self._env.mode is not RuntimeMode.FROZEN:
            return

        if self._server is None:
            return

        logger.info("Stopping in-process uvicorn server...")
        self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10.0)
        logger.info("In-process uvicorn server stopped.")

    def wait_until_ready(self, timeout: float = 60.0) -> bool:
        """
        Wait until the backend responds on /api/health and /app/ or timeout.

        Returns True if both endpoints appear to be available, False if the
        timeout elapses.
        """
        import urllib.error
        import urllib.request

        base = f"http://127.0.0.1:{self._env.backend_port}"
        health_url = f"{base}/api/health"
        frontend_url = f"{base}/app/"

        def _probe(url: str) -> bool:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    code = resp.getcode()
                    return 200 <= code < 400
            except urllib.error.URLError:
                return False

        logger.info(
            "Waiting for backend at %s and frontend at %s...",
            health_url,
            frontend_url,
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            backend_ok = _probe(health_url)
            frontend_ok = _probe(frontend_url)
            if backend_ok and frontend_ok:
                logger.info("Backend and frontend are ready.")
                return True
            time.sleep(1.0)

        logger.warning(
            "Timeout waiting for backend/frontend readiness; continuing anyway."
        )
        return False

    # ------------------------------- internals -----------------------------

    def _start_inprocess(self) -> None:
        """Start uvicorn.Server with backend.src.main:app in a background thread."""
        if self._server is not None:
            logger.info("In-process uvicorn server already started.")
            return

        config = uvicorn.Config(
            app=fastapi_app,
            host="127.0.0.1",
            port=self._env.backend_port,
            log_level="info",
        )
        server = uvicorn.Server(config=config)
        self._server = server

        def _run() -> None:
            try:
                logger.info(
                    "Starting in-process uvicorn server on http://127.0.0.1:%d",
                    self._env.backend_port,
                )
                server.run()
            except Exception:  # noqa: BLE001
                logger.exception("In-process uvicorn server crashed.")

        thread = threading.Thread(target=_run, name="uvicorn-inprocess", daemon=True)
        self._thread = thread
        thread.start()


# --------------------------------------------------------------------------- tray UI (frozen mode)


class TrayUIController:
    """
    Simple Qt-based system tray UI for the frozen runtime.

    Responsibilities:
    - Show a tray icon using the EDCA icon.
    - Provide "Open Web UI" and "Exit" actions.
    - Stop the backend server cleanly on exit.
    """

    def __init__(self, app: QApplication, env: RuntimeEnvironment, backend: BackendServerController) -> None:
        self._app = app
        self._env = env
        self._backend = backend

        self._tray = QSystemTrayIcon()
        self._configure_tray_icon()
        self._create_menu()

        # Treat clicking the tray icon itself as a large "Open Web UI" button.
        # Left-click or double-click on the tray icon will open the web UI,
        # in addition to the explicit "Open Web UI" menu item.
        self._tray.activated.connect(self._on_tray_activated)  # type: ignore[arg-type]

    # -------------------- setup ------------------------------------------------

    def _configure_tray_icon(self) -> None:
        icon_path = self._env.icon_path
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        self._tray.setToolTip("Elite: Dangerous Colonization Assistant")
        self._tray.setVisible(True)

    def _create_menu(self) -> None:
        menu = QMenu()
        open_action = menu.addAction("Open Web UI")
        open_action.triggered.connect(self._on_open_web_ui)  # type: ignore[arg-type]

        menu.addSeparator()
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._on_exit)  # type: ignore[arg-type]

        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """
        Handle clicks on the tray icon itself.

        This effectively turns the tray icon into a large "Open Web UI" button:
        a left-click or double-click will open the browser to the frontend URL.
        """
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._on_open_web_ui()

    # -------------------- actions ---------------------------------------------

    def _on_open_web_ui(self) -> None:
        url = self._env.frontend_url
        logger.info("Opening web UI at %s", url)
        webbrowser.open(url)

    def _on_exit(self) -> None:
        logger.info("Exit requested from tray menu.")
        # Confirm with the user to avoid accidental shutdown.
        reply = QMessageBox.question(
            None,
            "Exit ED Colonization Assistant",
            "Are you sure you want to exit EDCA?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._backend.stop()
        finally:
            self._tray.setVisible(False)
            self._app.quit()

    # -------------------- public API ------------------------------------------

    def show(self) -> None:
        # Nothing extra to do at the moment; kept for symmetry / extension.
        self._tray.show()


# --------------------------------------------------------------------------- runtime application


class RuntimeApplication:
    """
    Top-level application orchestrator.

    - In DEV mode:
      Delegates to the existing launcher window and venv-based startup so
      that developers continue to use the same tooling as before.

    - In FROZEN mode:
      Starts the backend in-process and presents a tray icon that can open
      the web UI and exit the application.
    """

    def __init__(self) -> None:
        self._env = RuntimeEnvironment.detect()
        self._backend = BackendServerController(self._env)

    def run(self) -> int:
        if self._env.mode is RuntimeMode.DEV:
            logger.info("RuntimeApplication starting in DEV mode.")
            return self._run_dev()

        logger.info("RuntimeApplication starting in FROZEN mode.")
        return self._run_frozen()

    # -------------------- DEV mode -------------------------------------------

    def _run_dev(self) -> int:
        """
        Development mode behaviour.

        This reuses the existing launcher window (`backend/src/launcher.py`)
        exactly as before, so that developer workflows are unchanged.
        """
        from PySide6.QtCore import QTimer  # imported lazily for speed
        from .launcher import Launcher, QtLaunchWindow

        app = QApplication([])
        window = QtLaunchWindow(self._env.project_root)
        window.show()

        launcher = Launcher(self._env.project_root, window)

        def _start() -> None:
            launcher.run()

        QTimer.singleShot(0, _start)
        return app.exec()

    # -------------------- FROZEN mode ----------------------------------------

    def _run_frozen(self) -> int:
        """
        Frozen (packaged EXE) behaviour.

        - Starts the backend in-process.
        - Waits for readiness (health + /app).
        - Shows a tray icon with Open Web UI / Exit.
        """
        app = QApplication([])
        app.setApplicationName("Elite: Dangerous Colonization Assistant")
        app.setQuitOnLastWindowClosed(False)

        # Ensure the runtime EXE has the correct icon in the Windows taskbar.
        # In frozen mode this process is the Nuitka-built EDColonizationAsst.exe,
        # not python.exe, so Qt will use this icon for the taskbar button.
        icon_path = self._env.icon_path
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

        # Start backend in-process.
        self._backend.start()
        self._backend.wait_until_ready(timeout=60.0)

        # Create and show tray UI.
        tray = TrayUIController(app, self._env, self._backend)
        tray.show()

        # Optionally auto-open the web UI on first run.
        webbrowser.open(self._env.frontend_url)

        return app.exec()


# --------------------------------------------------------------------------- entrypoint


def main() -> int:
    runtime_app = RuntimeApplication()
    return runtime_app.run()


if __name__ == "__main__":
    raise SystemExit(main())