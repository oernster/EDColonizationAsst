"""Tests for the ApplicationInstanceLock singleton runtime helper.

These tests exercise the real locking behaviour using the filesystem and
OS-level file locks; no external mocking frameworks are used. The aim is
to validate that:

- A first lock instance can acquire and hold the lock.
- A second instance in the same process cannot acquire the lock while it is held.
- Once the first instance releases the lock, a second instance can acquire it.
- The lock file path is resolved to a per-user, writable directory on both
  Windows and POSIX-like platforms.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import src.runtime.app_singleton as app_singleton_mod
from src.runtime.app_singleton import (
    ApplicationInstanceLock,
    ApplicationInstanceLockError,
)


def _make_isolated_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ApplicationInstanceLock:
    """Create an ApplicationInstanceLock that writes into a temp directory.

    We override the relevant environment variables so that _resolve_lock_path()
    points inside tmp_path instead of any real user directory.
    """
    # Force a predictable base directory for the lock file on all platforms.
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    else:
        # Prefer XDG_RUNTIME_DIR on POSIX, consistent with the implementation.
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "xdg_runtime"))

    return ApplicationInstanceLock(app_id="edca_test")


def test_acquire_and_release_lock_allows_single_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First instance acquires the lock, second instance in the same process cannot.

    After releasing the first lock, a second instance should be able to acquire it.
    """
    lock1 = _make_isolated_lock(tmp_path, monkeypatch)
    lock2 = _make_isolated_lock(tmp_path, monkeypatch)

    # First acquisition should succeed.
    assert lock1.acquire() is True

    # Second acquisition (same app_id, same process) should fail while held.
    assert lock2.acquire() is False

    # After releasing the first lock, the second should be able to acquire it.
    lock1.release()
    assert lock2.acquire() is True

    # Clean up explicitly to release OS resources.
    lock2.release()


def test_context_manager_raises_when_lock_already_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Using the lock as a context manager should raise if another instance holds it."""
    lock1 = _make_isolated_lock(tmp_path, monkeypatch)
    lock2 = _make_isolated_lock(tmp_path, monkeypatch)

    assert lock1.acquire() is True

    with pytest.raises(ApplicationInstanceLockError):
        with lock2:
            pass  # pragma: no cover  # The body is never executed

    # Ensure we can still release the original lock cleanly.
    lock1.release()


def test_resolve_lock_path_uses_per_user_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_resolve_lock_path() should return a path under a per-user directory."""
    lock = _make_isolated_lock(tmp_path, monkeypatch)
    path = lock._resolve_lock_path()  # type: ignore[attr-defined]

    # The filename must include the app_id and a .lock suffix.
    assert path.name == "edca_test.lock"

    # On Windows we expect the path to live under LOCALAPPDATA; on POSIX it
    # will use XDG_RUNTIME_DIR (overridden in _make_isolated_lock).
    if os.name == "nt":
        base = Path(os.environ["LOCALAPPDATA"]) / "EDColonisationAsst"
    else:
        base = Path(os.environ["XDG_RUNTIME_DIR"]) / "edca"

    assert path.parent == base
    # The directory should have been created by _resolve_lock_path().
    assert path.parent.exists()


def test_acquire_twice_on_same_instance_returns_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Calling acquire() twice on the same instance should succeed both times.

    The second call should hit the early-return branch that detects an
    already-held lock within the same process.
    """
    lock = _make_isolated_lock(tmp_path, monkeypatch)

    assert lock.acquire() is True
    # Second acquisition on the same instance should be a no-op True.
    assert lock.acquire() is True

    lock.release()


def test_acquire_raises_application_lock_error_when_open_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """acquire() should raise ApplicationInstanceLockError when file open fails."""

    lock = _make_isolated_lock(tmp_path, monkeypatch)

    failing_path = tmp_path / "nope" / "edca_test.lock"

    def fake_resolve_lock_path() -> Path:
        return failing_path

    # Replace the instance-specific _resolve_lock_path with our fake.
    monkeypatch.setattr(
        lock, "_resolve_lock_path", fake_resolve_lock_path, raising=False
    )

    def failing_open(_self: Path, *args, **kwargs):
        raise OSError("cannot open")

    # Patch the Path.open used inside the runtime app_singleton module so that
    # any attempt to open the lock file fails with an OSError.
    monkeypatch.setattr(app_singleton_mod.Path, "open", failing_open)

    with pytest.raises(ApplicationInstanceLockError):
        lock.acquire()


def test_acquire_propagates_internal_lock_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the underlying OS lock helper raises, acquire() should re-raise it.

    This exercises the error-handling path that closes the file handle and
    re-raises exceptions from the platform-specific lock functions.
    """
    lock = _make_isolated_lock(tmp_path, monkeypatch)

    def boom(_fh):
        raise RuntimeError("lock failed")

    if os.name == "nt":
        monkeypatch.setattr(
            app_singleton_mod.ApplicationInstanceLock,
            "_acquire_windows_lock",
            staticmethod(boom),
        )
    else:
        monkeypatch.setattr(
            app_singleton_mod.ApplicationInstanceLock,
            "_acquire_posix_lock",
            staticmethod(boom),
        )

    with pytest.raises(RuntimeError):
        lock.acquire()


def test_resolve_lock_path_raises_when_directory_cannot_be_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_resolve_lock_path should raise an error when mkdir fails for the lock dir."""
    # Point the module's environment variables at our tmp_path so that it
    # attempts to create a directory inside the test sandbox.
    if os.name == "nt":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    else:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))

    def failing_mkdir(self: Path, *args, **kwargs) -> None:
        raise OSError("mkdir failed")

    # Patch Path.mkdir used inside app_singleton to simulate a filesystem error.
    monkeypatch.setattr(app_singleton_mod.Path, "mkdir", failing_mkdir)

    lock = ApplicationInstanceLock(app_id="edca_test_mkdir")

    with pytest.raises(ApplicationInstanceLockError):
        # _resolve_lock_path is an internal helper; we call it directly to
        # isolate the directory-creation failure.
        _ = lock._resolve_lock_path()  # type: ignore[attr-defined]
