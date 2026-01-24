"""File watcher service for monitoring journal files."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from watchdog.observers import Observer

from .journal_parser import IJournalParser
from .system_tracker import ISystemTracker
from .journal_ingestion import JournalFileHandler
from ..repositories.colonisation_repository import IColonisationRepository
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IFileWatcher(ABC):
    """Interface for file watching."""

    @abstractmethod
    async def start_watching(self, directory: Path) -> None:
        """Start watching directory for changes."""
        raise NotImplementedError

    @abstractmethod
    async def stop_watching(self) -> None:
        """Stop watching directory."""
        raise NotImplementedError

    @abstractmethod
    def set_update_callback(self, callback: Callable) -> None:
        """Set callback for when data is updated."""
        raise NotImplementedError


class FileWatcher(IFileWatcher):
    """
    Watches the Elite: Dangerous journal directory for changes.

    Responsibilities:
    - Owns a watchdog Observer that tracks filesystem changes.
    - Creates and wires a JournalFileHandler instance to process journal
      files via the injected parser, system tracker and repository.
    - Optionally invokes an async update callback for each affected system.
    """

    def __init__(
        self,
        parser: IJournalParser,
        system_tracker: ISystemTracker,
        repository: IColonisationRepository,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.parser = parser
        self.system_tracker = system_tracker
        self.repository = repository
        self._observer: Optional[Observer] = None
        self._handler: Optional[JournalFileHandler] = None
        self._update_callback: Optional[Callable] = None
        # Event loop used to schedule async processing from watchdog threads.
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()

    def set_update_callback(self, callback: Callable) -> None:
        """
        Set callback for when data is updated.

        Args:
            callback: async function to call with system_name when updated.
        """
        self._update_callback = callback
        if self._handler is not None:
            self._handler.update_callback = callback

    async def start_watching(self, directory: Path) -> None:
        """
        Start watching a directory for changes.

        Args:
            directory: Path to journal directory.
        """
        if self._observer is not None:
            logger.warning("File watcher already running")
            return

        if not directory.exists():
            logger.error("Journal directory does not exist: %s", directory)
            raise FileNotFoundError(f"Journal directory not found: {directory}")

        # Create handler
        self._handler = JournalFileHandler(
            self.parser,
            self.system_tracker,
            self.repository,
            self._update_callback,
            loop=self._loop,
        )

        # Create and start observer
        self._observer = Observer()
        self._observer.schedule(self._handler, str(directory), recursive=False)
        self._observer.start()

        logger.info("Started watching journal directory: %s", directory)

        # Process existing files
        await self._process_existing_files(directory)

    async def stop_watching(self) -> None:
        """Stop watching directory."""
        if self._observer is None:
            return

        self._observer.stop()
        self._observer.join()
        self._observer = None
        self._handler = None

        logger.info("Stopped watching journal directory")

    async def _process_existing_files(self, directory: Path) -> None:
        """
        Process existing journal files in a directory.

        Args:
            directory: Path to journal directory.
        """
        logger.info("Processing existing journal files...")

        # Find all journal files
        journal_files = sorted(
            directory.glob("Journal.*.log"), key=lambda p: p.stat().st_mtime
        )

        if not journal_files:
            logger.warning("No existing journal files found")
            return

        # Process all existing files
        for file_path in journal_files:
            logger.info("Processing journal file: %s", file_path.name)
            if self._handler is not None:
                await self._handler._process_file(file_path)  # noqa: SLF001
