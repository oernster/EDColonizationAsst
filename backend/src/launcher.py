#!/usr/bin/env python3
"""
GUI launcher for Elite: Dangerous Colonization Assistant.

Responsibilities:
- Present a simple GUI with icon, title, status text, and a progress bar.
- Orchestrate initialization steps in order:
  1. Ensure Python virtual environment for backend exists.
  2. Install/upgrade backend dependencies via pip.
  3. Install frontend dependencies via npm (if needed).
  4. Start tray controller (which starts backend + frontend dev server).
  5. Optionally poll readiness of backend/frontend (HTTP endpoints).

Design goals:
- OO, SOLID, PEP 8 compliant where practical.
- Keep orchestration logic separate from the Qt view.
- Avoid leaking subprocess details into the UI layer.

NOTE:
This script assumes that PySide6 is importable by the Python interpreter
running it. For a production launcher that runs *before* any venv/requirements
are set up, this script should be compiled into a self-contained EXE using
Nuitka (similar to buildguiinstaller.py), bundling PySide6 inside the binary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)


APP_NAME = "Elite: Dangerous Colonization Assistant"
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
PROGRESS_MAX = 100


@dataclass(frozen=True)
class InitStep:
    """Represents a single initialization step."""

    name: str
    progress: int
    action: Callable[[], None]


class LaunchView:
    """Abstraction of the launcher UI for testability and SOLID compliance."""

    def set_status(self, message: str, progress: int) -> None:
        raise NotImplementedError

    def show_error(self, message: str) -> None:
        raise NotImplementedError

    def allow_open_frontend(self, url: str) -> None:
        raise NotImplementedError

    def process_events(self) -> None:
        raise NotImplementedError


class QtLaunchWindow(QMainWindow, LaunchView):
    """Simple launcher window with icon, title, status label, and progress bar."""

    def __init__(self, project_root: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project_root = project_root
        self._frontend_url: Optional[str] = None

        self.setWindowTitle(f"{APP_NAME} Launcher")
        # Taller window to comfortably fit a larger app icon and primary button.
        self.setFixedSize(420, 360)
        self._init_ui()

    def _init_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(self)

        # STRICTLY use the PNG for the in-window artwork so it renders crisply.
        # We intentionally do NOT fall back to the ICO here; if the PNG cannot
        # be loaded, the label will remain empty so the problem is obvious.
        png_path = self._project_root / "EDColonizationAsst.png"

        pixmap = QPixmap()
        if png_path.exists():
            pixmap = QPixmap(str(png_path))

        if not pixmap.isNull():
            scaled = pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(scaled)

        icon_label.setMinimumSize(160, 160)
        icon_label.setAlignment(Qt.AlignHCenter)

        # Title
        title_label = QLabel(APP_NAME, self)
        title_label.setAlignment(Qt.AlignHCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        # Status label
        self._status_label = QLabel("Initialising...", self)
        self._status_label.setAlignment(Qt.AlignHCenter)
        self._status_label.setWordWrap(True)

        # Progress bar
        self._progress = QProgressBar(self)
        self._progress.setRange(0, PROGRESS_MAX)
        self._progress.setValue(0)
        self._progress.setFormat("%p%")
        self._progress.setTextVisible(True)

        # "Open UI" button (enabled when ready) – make it visually prominent.
        self._open_button = QPushButton("Open Web UI", self)
        self._open_button.setEnabled(False)
        self._open_button.setMinimumHeight(40)
        self._open_button.setMinimumWidth(200)
        self._open_button.setStyleSheet(
            "font-size: 13px; font-weight: 600; padding: 8px 24px;"
        )
        self._open_button.clicked.connect(self._on_open_clicked)

        layout.addWidget(icon_label)
        # Extra space so the large icon does not visually collide with the title.
        layout.addSpacing(12)
        layout.addWidget(title_label)
        layout.addSpacing(8)
        layout.addWidget(self._status_label)
        layout.addWidget(self._progress)
        layout.addSpacing(12)
        layout.addWidget(self._open_button, alignment=Qt.AlignHCenter)

        central.setLayout(layout)
        self.setCentralWidget(central)

    # LaunchView implementation -------------------------------------------------

    def set_status(self, message: str, progress: int) -> None:
        self._status_label.setText(message)
        self._progress.setValue(progress)
        self.process_events()

    def show_error(self, message: str) -> None:
        # For now, just show it prominently in the status label.
        self._status_label.setText(f"ERROR: {message}")
        self._progress.setValue(0)
        self.process_events()

    def allow_open_frontend(self, url: str) -> None:
        self._frontend_url = url
        self._open_button.setEnabled(True)
        self.process_events()

    def process_events(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    # ------------------------------------------------------------------ slots

    def _on_open_clicked(self) -> None:
        if self._frontend_url:
            webbrowser.open(self._frontend_url)


class Launcher:
    """Orchestrates initialization steps and updates the view."""

    def __init__(self, project_root: Path, view: LaunchView) -> None:
        self._project_root = project_root
        self._view = view
        self._backend_dir = project_root / "backend"
        self._frontend_dir = project_root / "frontend"
        self._venv_python = self._backend_dir / "venv" / "Scripts" / "python.exe"
        self._log_path = project_root / "run-edca.log"

    # Public API -------------------------------------------------------

    def run(self) -> None:
        """Run all initialization steps, updating the view."""
        try:
            steps = self._build_steps()
            for step in steps:
                self._view.set_status(step.name, step.progress)
                step.action()
            # Once all steps are done, allow opening the UI served by the backend.
            frontend_url = f"http://127.0.0.1:{BACKEND_PORT}/app/"
            self._view.set_status(f"Ready. Open {frontend_url}", PROGRESS_MAX)
            self._view.allow_open_frontend(frontend_url)
        except Exception as exc:  # noqa: BLE001
            self._view.show_error(str(exc))

    # Step construction ------------------------------------------------

    def _build_steps(self) -> List[InitStep]:
        """
        Define the ordered initialisation steps for the launcher.

        Note that we no longer install or start the frontend via npm at
        runtime. Instead, the frontend is expected to be built ahead of
        time (e.g. `npm run build`) and served as static files by the
        backend. This removes any Node.js/npm requirement for end users.
        """
        return [
            InitStep("Checking Python environment...", 5, self._check_python),
            InitStep("Ensuring backend virtual environment...", 20, self._ensure_venv),
            InitStep("Installing backend dependencies...", 45, self._install_backend_deps),
            InitStep("Starting services...", 75, self._start_services),
            InitStep("Waiting for web UI to become available...", 95, self._wait_for_readiness),
        ]

    # Individual actions -----------------------------------------------

    def _check_python(self) -> None:
        """Ensure that some python is available."""
        try:
            result = subprocess.run(
                ["python", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(f"Python is required but was not found: {exc}") from exc

        self._append_log(f"[launcher] System python: {result.stdout.strip()}")

    def _ensure_venv(self) -> None:
        """Create backend/venv if missing."""
        if self._venv_python.exists():
            self._append_log(f"[launcher] Using existing venv: {self._venv_python}")
            return

        self._append_log("[launcher] Creating backend/venv...")
        cmd = ["python", "-m", "venv", str(self._backend_dir / "venv")]
        self._run_subprocess(cmd, cwd=self._project_root, label="create venv")

    def _install_backend_deps(self) -> None:
        """Install backend Python dependencies into the venv.

        In an installed environment the venv will typically already have had
        its dependencies installed successfully by a previous run. If this
        step fails (for example due to a transient network issue), we log a
        warning and continue using the existing environment instead of
        treating it as a hard error that blocks the launcher UI.
        """
        if not self._venv_python.exists():
            # If the venv python is missing entirely, subsequent steps are
            # unlikely to succeed, so this is still considered fatal.
            raise RuntimeError(
                "Virtual environment python.exe is missing; cannot install backend deps."
            )

        requirements = self._backend_dir / "requirements.txt"
        if not requirements.exists():
            self._append_log(
                "[launcher] backend/requirements.txt not found; skipping backend deps install."
            )
            return

        self._append_log(f"[launcher] Installing backend dependencies from {requirements}...")
        cmd = [str(self._venv_python), "-m", "pip", "install", "-r", str(requirements)]
        try:
            self._run_subprocess(cmd, cwd=self._project_root, label="install backend deps")
        except RuntimeError as exc:
            # Log the error but continue with the existing environment so that
            # users with an already-populated venv are not blocked by a
            # subsequent pip failure.
            self._append_log(
                "[launcher] WARNING: Backend dependency installation failed but "
                f"continuing with existing environment: {exc}"
            )

    def _start_services(self) -> None:
        """
        Start tray controller using the venv python.

        The tray controller is responsible for starting the backend (uvicorn)
        and frontend (Vite dev server) in the background.
        """
        if not self._venv_python.exists():
            raise RuntimeError("Virtual environment python.exe is missing; cannot start services.")

        tray_script = self._backend_dir / "src" / "tray_app.py"
        if not tray_script.exists():
            raise RuntimeError(f"Tray script not found at {tray_script}")

        self._append_log("[launcher] Starting tray controller...")
        # Launch tray in the background; we do not wait here, readiness is
        # checked separately.
        if sys.platform.startswith("win"):
            CREATE_NO_WINDOW = 0x08000000
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(
                [str(self._venv_python), str(tray_script)],
                cwd=str(self._project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                startupinfo=startup_info,
            )
        else:
            subprocess.Popen(
                [str(self._venv_python), str(tray_script)],
                cwd=str(self._project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _wait_for_readiness(self) -> None:
        """Poll backend API and frontend UI endpoints until they respond or timeout."""
        import urllib.error
        import urllib.request

        def _probe(url: str) -> bool:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    return 200 <= resp.getcode() < 500
            except urllib.error.URLError:
                return False

        # Backend health endpoint and static frontend served by the backend.
        backend_health = f"http://127.0.0.1:{BACKEND_PORT}/api/health"
        frontend_url = f"http://127.0.0.1:{BACKEND_PORT}/app/"

        deadline = time.time() + 60.0  # 60 seconds
        self._append_log(
            "[launcher] Waiting for backend at "
            f"{backend_health} and frontend at {frontend_url}..."
        )

        while time.time() < deadline:
            backend_ok = _probe(backend_health)
            frontend_ok = _probe(frontend_url)
            if backend_ok and frontend_ok:
                self._append_log("[launcher] Backend and frontend are ready.")
                return
            # Light backoff and keep GUI responsive.
            self._view.process_events()
            time.sleep(1.0)

        self._append_log("[launcher] Timeout waiting for backend/frontend readiness; continuing anyway.")

    # Helpers -----------------------------------------------------------

    def _run_subprocess(self, cmd: List[str], cwd: Path, label: str) -> None:
        """Run a subprocess synchronously, raising on error and logging output."""
        self._append_log(f"[launcher] Running ({label}): {' '.join(cmd)} (cwd={cwd})")
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to start process for {label}: {exc}") from exc

        # Stream output to log while keeping UI responsive.
        assert proc.stdout is not None
        for line in proc.stdout:
            self._append_log(line.rstrip("\n"))
            self._view.process_events()

        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"Command for '{label}' failed with exit code {ret}")

    def _append_log(self, message: str) -> None:
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        except OSError:
            # Logging failures should not break the launcher.
            pass


def _detect_project_root() -> Path:
    """Detect project root from this file location."""
    return Path(__file__).resolve().parents[2]


def main() -> int:
    project_root = _detect_project_root()

    app = QApplication(sys.argv)

    # Ensure the taskbar / application icon is set for the launcher process.
    # Prefer the PNG (wrapped in a QIcon) for a crisp icon; fall back to the ICO.
    png_path = project_root / "EDColonizationAsst.png"
    ico_path = project_root / "EDColonizationAsst.ico"
    if png_path.exists():
        app.setWindowIcon(QIcon(str(png_path)))
    elif ico_path.exists():
        app.setWindowIcon(QIcon(str(ico_path)))

    window = QtLaunchWindow(project_root)
    window.show()

    # Kick off initialization after the event loop has had a chance to show the window.
    launcher = Launcher(project_root, window)

    def _start() -> None:
        launcher.run()

    QTimer.singleShot(0, _start)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())