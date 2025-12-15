from __future__ import annotations

"""Tests for the tray controller entrypoint.

These tests exercise the top-level [`main()`](backend/src/tray_app.py:293)
function in a controlled way, focusing on its interaction with the
[`ApplicationInstanceLock`](backend/src/runtime/app_singleton.py:1):

- When the lock is already held, `main()` should exit quickly without
  creating any Qt objects.
- When acquiring the lock raises `ApplicationInstanceLockError`, `main()`
  should still construct a `QApplication`, create a
  [`TrayController`](backend/src/tray_app.py:62), and return the Qt exit
  code from `QApplication.exec()`.
"""

from typing import Dict

import pytest

import src.tray_app as tray_app


def test_main_exits_early_when_lock_already_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the tray lock is already held, main() should exit early.

    Expected behaviour:

    - [`ApplicationInstanceLock.acquire()`](backend/src/runtime/app_singleton.py:1)
      returns False.
    - [`tray_app.main()`](backend/src/tray_app.py:293) immediately returns 0.
    - No `QApplication` instance is ever constructed.
    """

    class DummyLock:
        def __init__(self) -> None:  # pragma: no cover - trivial
            pass

        def acquire(self) -> bool:
            # Simulate another tray instance already holding the lock.
            return False

    # Ensure our dummy lock is used.
    monkeypatch.setattr(tray_app, "ApplicationInstanceLock", DummyLock)

    # Guard against accidental QApplication construction. If main() tried to
    # construct a QApplication in this scenario, this sentinel would be
    # instantiated and the test would fail.
    class SentinelApp:
        def __init__(self, *_args, **_kwargs) -> None:  # pragma: no cover - defensive
            raise AssertionError(
                "QApplication should not be constructed when lock is already held"
            )

    monkeypatch.setattr(tray_app, "QApplication", SentinelApp)

    code = tray_app.main()

    assert code == 0
    # We do not assert on opened URL here because tray_app.main() intentionally
    # just exits when the tray lock is held, leaving the existing tray instance
    # to continue managing the backend and frontend.


def test_main_continues_when_lock_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the tray lock cannot be created, main() should still start Qt.

    Scenario:

    - [`ApplicationInstanceLock.acquire()`](backend/src/runtime/app_singleton.py:1)
      raises `ApplicationInstanceLockError`.
    - The exception is caught inside [`tray_app.main()`](backend/src/tray_app.py:293).
    - A `QApplication` is created and its `exec()` method is invoked.
    - A [`TrayController`](backend/src/tray_app.py:62) is instantiated.
    - The return code from `exec()` is propagated as the process exit code.
    """

    class DummyLock:
        def __init__(self) -> None:  # pragma: no cover - trivial
            pass

        def acquire(self) -> bool:
            raise tray_app.ApplicationInstanceLockError("simulated lock failure")

    calls: Dict[str, bool | int] = {}

    class DummyApp:
        def __init__(self, *_args, **_kwargs) -> None:
            calls["app_created"] = True

        def setQuitOnLastWindowClosed(self, flag: bool) -> None:  # noqa: N802
            calls["quit_on_last_window_closed"] = flag

        def exec(self) -> int:
            calls["exec_called"] = True
            return 7

    class DummyController:
        def __init__(self, app: DummyApp) -> None:
            calls["controller_created"] = True
            calls["controller_app_is_dummy"] = isinstance(app, DummyApp)

    monkeypatch.setattr(tray_app, "ApplicationInstanceLock", DummyLock)
    monkeypatch.setattr(tray_app, "QApplication", DummyApp)
    monkeypatch.setattr(tray_app, "TrayController", DummyController)

    code = tray_app.main()

    assert code == 7
    assert calls["app_created"] is True
    assert calls["exec_called"] is True
    assert calls["controller_created"] is True
    assert calls["controller_app_is_dummy"] is True
    assert calls["quit_on_last_window_closed"] is False
