from __future__ import annotations

"""
Core runtime orchestration for the packaged and development runtimes.

This module contains the bulk of the logic that was previously embedded in
[`runtime_entry`](backend/src/runtime_entry.py:1):

- [`BackendServerController`] controls the FastAPI backend server, starting an
  in-process uvicorn.Server in frozen mode.
- [`TrayUIController`] owns the Qt system tray UI for the frozen runtime.
- [`RuntimeApplication`] coordinates DEV vs FROZEN behaviour.

Keeping these classes here allows runtime_entry.py to remain a thin entrypoint
focused on single-instance enforcement and crash logging.
"""

import threading
import time
import webbrowser
from typing import Optional

import uvicorn
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from .common import _debug_log, fastapi_app, logger
from .environment import RuntimeEnvironment
from .common import RuntimeMode


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
        _debug_log(f"[BackendServerController] start() mode={self._env.mode}")
        if self._env.mode is RuntimeMode.FROZEN:
            self._start_inprocess()
        else:
            # For now DEV mode is handled by the existing launcher; we leave
            # this hook in place for possible future use.
            logger.info(
                "BackendServerController.start() called in DEV mode; "
                "no-op (launcher handles backend in development).",
            )

    def stop(self) -> None:
        """Stop the backend server if it was started in-process."""
        _debug_log(f"[BackendServerController] stop() mode={self._env.mode}")
        if self._env.mode is not RuntimeMode.FROZEN:
            _debug_log("[BackendServerController] stop() no-op in DEV mode")
            return

        if self._server is None:
            _debug_log(
                "[BackendServerController] stop() called with no server instance",
            )
            return

        logger.info("Stopping in-process uvicorn server...")
        self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10.0)
        logger.info("In-process uvicorn server stopped.")
        _debug_log("[BackendServerController] in-process uvicorn server stopped")

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
        _debug_log(
            "[BackendServerController] wait_until_ready() "
            f"health_url={health_url} frontend_url={frontend_url} timeout={timeout}",
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            backend_ok = _probe(health_url)
            frontend_ok = _probe(frontend_url)
            if backend_ok and frontend_ok:
                logger.info("Backend and frontend are ready.")
                _debug_log(
                    "[BackendServerController] backend/frontend reported ready",
                )
                return True
            time.sleep(1.0)

        logger.warning(
            "Timeout waiting for backend/frontend readiness; continuing anyway.",
        )
        _debug_log("[BackendServerController] wait_until_ready() timed out")
        return False

    # ------------------------------- internals -----------------------------

    def _start_inprocess(self) -> None:
        """
        Start uvicorn.Server with backend.src.main:app in a background thread.

        In the frozen onefile build, uvicorn's default logging configuration can
        fail when it tries to attach a colourising formatter to a handler whose
        stream does not expose 'isatty()' in the way it expects. This manifests
        as:

            ValueError("Unable to configure formatter 'default'")

        when uvicorn.Config.configure_logging() calls logging.config.dictConfig.

        To avoid this entirely, we subclass uvicorn.Config and override
        configure_logging() as a no-op so that uvicorn does not touch the
        logging configuration at all. We then rely solely on the application's
        logging configuration from backend.src.utils.logger.setup_logging().
        """
        if self._server is not None:
            logger.info("In-process uvicorn server already started.")
            _debug_log(
                "[BackendServerController] _start_inprocess() called but server already running",
            )
            return

        class _QuietUvicornConfig(uvicorn.Config):
            def configure_logging(self) -> None:  # type: ignore[override]
                # Do not let uvicorn interfere with logging setup in the frozen
                # runtime.
                return

        # Derive the bind host from the application's configuration so that
        # we can listen on 0.0.0.0 when configured, allowing LAN access.
        try:
            try:
                from .config import get_config  # type: ignore[import-not-found]
            except ImportError:
                from backend.src.config import get_config  # type: ignore[import-error]

            _cfg = get_config()
            host = (
                getattr(getattr(_cfg, "server", _cfg), "host", "127.0.0.1")
                or "127.0.0.1"
            )
        except Exception as exc:  # noqa: BLE001
            host = "127.0.0.1"
            _debug_log(
                "[BackendServerController] Failed to read config for host; "
                f"defaulting to 127.0.0.1: {exc!r}",
            )

        _debug_log(
            "[BackendServerController] starting in-process uvicorn on "
            f"{host}:{self._env.backend_port}",
        )

        config = _QuietUvicornConfig(
            app=fastapi_app,
            host=host,
            port=self._env.backend_port,
            log_level="info",
            log_config=None,
        )
        server = uvicorn.Server(config=config)
        self._server = server

        def _run() -> None:
            try:
                logger.info(
                    "Starting in-process uvicorn server on http://%s:%d",
                    host,
                    self._env.backend_port,
                )
                _debug_log(
                    "[BackendServerController] uvicorn.Server.run() starting on "
                    f"{host}:{self._env.backend_port}",
                )
                server.run()
                _debug_log(
                    "[BackendServerController] uvicorn.Server.run() returned normally",
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("In-process uvicorn server crashed.")
                _debug_log(
                    "[BackendServerController] In-process uvicorn server crashed: "
                    f"{exc!r}",
                )

        thread = threading.Thread(
            target=_run,
            name="uvicorn-inprocess",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        _debug_log("[BackendServerController] uvicorn-inprocess thread started")


class TrayUIController:
    """
    Simple Qt-based system tray UI for the frozen runtime.

    Responsibilities:
    - Show a tray icon using the EDCA icon.
    - Provide "Open Web UI" and "Exit" actions.
    - Stop the backend server cleanly on exit.
    """

    def __init__(
        self,
        app: QApplication,
        env: RuntimeEnvironment,
        backend: BackendServerController,
    ) -> None:
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
        _debug_log(
            "[RuntimeApplication] detected environment: "
            f"mode={self._env.mode}, project_root={self._env.project_root}",
        )

    def run(self) -> int:
        if self._env.mode is RuntimeMode.DEV:
            logger.info("RuntimeApplication starting in DEV mode.")
            _debug_log("[RuntimeApplication] run() entering DEV mode")
            return self._run_dev()

        logger.info("RuntimeApplication starting in FROZEN mode.")
        _debug_log("[RuntimeApplication] run() entering FROZEN mode")
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
        _debug_log("[RuntimeApplication] _run_frozen() starting")
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
        _debug_log("[RuntimeApplication] starting in-process backend")
        self._backend.start()
        ready = self._backend.wait_until_ready(timeout=60.0)
        _debug_log(
            "[RuntimeApplication] backend readiness wait completed; " f"ready={ready}",
        )

        # Create and show tray UI.
        tray = TrayUIController(app, self._env, self._backend)
        tray.show()
        _debug_log("[RuntimeApplication] TrayUIController created and shown")

        # Optionally auto-open the web UI on first run.
        webbrowser.open(self._env.frontend_url)
        _debug_log(
            "[RuntimeApplication] Opening web UI at " f"{self._env.frontend_url}",
        )

        result = app.exec()
        _debug_log(
            f"[RuntimeApplication] Qt event loop exited with code {result}",
        )
        return result


__all__ = ["BackendServerController", "TrayUIController", "RuntimeApplication"]
