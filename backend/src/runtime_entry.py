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
import sys

import uvicorn
from fastapi import FastAPI
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon


def _debug_log(message: str) -> None:
    """
    Lightweight debug logger for the frozen runtime.

    Writes to EDColonizationAsst-runtime.log next to the EXE so that we can
    see how far startup progresses even if the Qt tray/icon never appears.
    This deliberately does not depend on the backend logging config.
    """
    try:
        try:
            exe_dir = Path(sys.argv[0]).resolve().parent
        except Exception:
            exe_dir = Path.cwd()

        log_path = exe_dir / "EDColonizationAsst-runtime.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        # Never let debug logging break the runtime.
        pass

# Import FastAPI app and runtime utilities. In normal (package) execution the
# relative imports work (backend.src.runtime_entry). In the frozen Nuitka
# onefile build the module is executed as a top-level script so relative
# imports can fail with "attempted relative import with no known parent
# package". We attempt both relative and absolute imports and log any fatal
# failure to the lightweight runtime log.
try:
    try:
        from .main import app as fastapi_app
        from .utils.logger import get_logger, setup_logging
        from .utils.runtime import RuntimeMode, get_runtime_mode
    except Exception:
        from backend.src.main import app as fastapi_app
        from backend.src.utils.logger import get_logger, setup_logging
        from backend.src.utils.runtime import RuntimeMode, get_runtime_mode
except Exception as exc:
    _debug_log(f"[runtime_entry] FATAL importing FastAPI app or runtime utilities: {exc!r}")
    # Re-raise so Nuitka/console still see the failure, but we at least have
    # EDColonizationAsst-runtime.log with the cause.
    raise

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
        """
        Best-effort resolution of the EDCA icon on disk.

        In a frozen onefile build we prefer the install directory that contains
        EDColonizationAsst.exe (so that the tray and any Qt surfaces use the
        same icon as the runtime EXE). In dev mode we fall back to the
        project_root next to backend/, which matches the existing layout.
        """
        candidates: list[Path] = []

        # 1) Directory of the running executable (frozen) or script (dev).
        try:
            exe_dir = Path(sys.argv[0]).resolve().parent
            candidates.append(exe_dir / "EDColonizationAsst.ico")
        except Exception:
            pass

        # 2) Project root as detected by RuntimeEnvironment.detect().
        candidates.append(self.project_root / "EDColonizationAsst.ico")

        for path in candidates:
            if path.exists():
                return path

        # 3) Fallback: return the executable path itself so Qt can still
        # extract an icon resource from the EXE if available.
        try:
            return Path(sys.argv[0]).resolve()
        except Exception:
            return self.project_root

    @classmethod
    def detect(cls) -> "RuntimeEnvironment":
        """
        Detect the current runtime environment, including a sensible project root.

        - In DEV mode we keep using the source layout
          (backend/src/runtime_entry.py -> src -> backend -> project_root).
        - In FROZEN mode we treat the directory containing the runtime EXE as
          the project root, which is also where the installer places the icon
          and other payload files.
        """
        mode = get_runtime_mode()

        if mode is RuntimeMode.FROZEN:
            try:
                project_root = Path(sys.argv[0]).resolve().parent
            except Exception:
                project_root = Path(__file__).resolve().parents[2]
        else:
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
        _debug_log(f"[BackendServerController] start() mode={self._env.mode}")
        if self._env.mode is RuntimeMode.FROZEN:
            self._start_inprocess()
        else:
            # For now DEV mode is handled by the existing launcher; we leave
            # this hook in place for possible future use.
            logger.info(
                "BackendServerController.start() called in DEV mode; "
                "no-op (launcher handles backend in development)."
            )
 
    def stop(self) -> None:
        """Stop the backend server if it was started in-process."""
        _debug_log(f"[BackendServerController] stop() mode={self._env.mode}")
        if self._env.mode is not RuntimeMode.FROZEN:
            _debug_log("[BackendServerController] stop() no-op in DEV mode")
            return
 
        if self._server is None:
            _debug_log("[BackendServerController] stop() called with no server instance")
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
            f"[BackendServerController] wait_until_ready() "
            f"health_url={health_url} frontend_url={frontend_url} timeout={timeout}"
        )
 
        deadline = time.time() + timeout
        while time.time() < deadline:
            backend_ok = _probe(health_url)
            frontend_ok = _probe(frontend_url)
            if backend_ok and frontend_ok:
                logger.info("Backend and frontend are ready.")
                _debug_log("[BackendServerController] backend/frontend reported ready")
                return True
            time.sleep(1.0)
 
        logger.warning(
            "Timeout waiting for backend/frontend readiness; continuing anyway."
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
            _debug_log("[BackendServerController] _start_inprocess() called but server already running")
            return
 
        class _QuietUvicornConfig(uvicorn.Config):
            def configure_logging(self) -> None:  # type: ignore[override]
                # Do not let uvicorn interfere with logging setup in the frozen runtime.
                return
 
        # Derive the bind host from the application's configuration so that
        # we can listen on 0.0.0.0 when configured, allowing LAN access.
        try:
            try:
                from .config import get_config  # type: ignore[import-not-found]
            except ImportError:
                from backend.src.config import get_config  # type: ignore[import-error]
 
            _cfg = get_config()
            host = getattr(getattr(_cfg, "server", _cfg), "host", "127.0.0.1") or "127.0.0.1"
        except Exception as exc:
            host = "127.0.0.1"
            _debug_log(f"[BackendServerController] Failed to read config for host; defaulting to 127.0.0.1: {exc!r}")
 
        _debug_log(
            f"[BackendServerController] starting in-process uvicorn on {host}:{self._env.backend_port}"
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
                    f"[BackendServerController] uvicorn.Server.run() starting on {host}:{self._env.backend_port}"
                )
                server.run()
                _debug_log("[BackendServerController] uvicorn.Server.run() returned normally")
            except Exception as exc:  # noqa: BLE001
                logger.exception("In-process uvicorn server crashed.")
                _debug_log(f"[BackendServerController] In-process uvicorn server crashed: {exc!r}")
 
        thread = threading.Thread(target=_run, name="uvicorn-inprocess", daemon=True)
        self._thread = thread
        thread.start()
        _debug_log("[BackendServerController] uvicorn-inprocess thread started")


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
        _debug_log(f"[RuntimeApplication] detected environment: mode={self._env.mode}, project_root={self._env.project_root}")
 
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
        _debug_log(f"[RuntimeApplication] backend readiness wait completed; ready={ready}")
 
        # Create and show tray UI.
        tray = TrayUIController(app, self._env, self._backend)
        tray.show()
        _debug_log("[RuntimeApplication] TrayUIController created and shown")
 
        # Optionally auto-open the web UI on first run.
        webbrowser.open(self._env.frontend_url)
        _debug_log(f"[RuntimeApplication] Opening web UI at {self._env.frontend_url}")
 
        result = app.exec()
        _debug_log(f"[RuntimeApplication] Qt event loop exited with code {result}")
        return result


# --------------------------------------------------------------------------- entrypoint




def main() -> int:
    """
    Entry point for the packaged runtime executable.

    In FROZEN mode this is invoked by the Nuitka-built EDColonizationAsst.exe.
    To make failures in the frozen runtime debuggable on end-user machines,
    we capture any unhandled exceptions and write them to a plain text log file
    next to the executable.
    """
    _debug_log("[runtime_entry] main() starting")

    try:
        runtime_app = RuntimeApplication()
        _debug_log(f"[runtime_entry] RuntimeApplication created; mode={runtime_app._env.mode}")  # type: ignore[attr-defined]
        result = runtime_app.run()
        _debug_log(f"[runtime_entry] RuntimeApplication.run() returned {result}")
        return result
    except Exception as exc:  # noqa: BLE001
        # Best-effort crash logging that does not depend on the backend logging
        # configuration or config.yaml being readable.
        import traceback  # type: ignore[import-not-found]

        try:
            exe_dir = Path(sys.argv[0]).resolve().parent
        except Exception:
            exe_dir = Path.cwd()

        log_path = exe_dir / "EDColonizationAsst-runtime-error.log"
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write("[runtime_entry] FATAL exception in packaged runtime\n")
                f.write(f"Exception: {exc!r}\n")
                f.write("Traceback:\n")
                f.write(traceback.format_exc())
                f.write("\n\n")
        except Exception:
            # Never let logging failures crash the process again.
            pass

        # Also emit something to stderr in case the process is started from a
        # console in development.
        try:
            print(f"[runtime_entry] FATAL: {exc!r}", file=sys.stderr)
        except Exception:
            pass

        _debug_log(f"[runtime_entry] FATAL exception: {exc!r}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())