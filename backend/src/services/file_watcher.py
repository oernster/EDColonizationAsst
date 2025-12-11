"""File watcher service for monitoring journal files"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
from .journal_parser import IJournalParser
from .system_tracker import ISystemTracker
from ..models.journal_events import (
    ColonizationConstructionDepotEvent,
    ColonizationContributionEvent,
    LocationEvent,
    FSDJumpEvent,
    DockedEvent,
)
from ..repositories.colonization_repository import IColonizationRepository
from ..models.colonization import ConstructionSite, Commodity
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IFileWatcher(ABC):
    """Interface for file watching"""

    @abstractmethod
    async def start_watching(self, directory: Path) -> None:
        """Start watching directory for changes"""
        pass

    @abstractmethod
    async def stop_watching(self) -> None:
        """Stop watching directory"""
        pass

    @abstractmethod
    def set_update_callback(self, callback: Callable) -> None:
        """Set callback for when data is updated"""
        pass


class JournalFileHandler(FileSystemEventHandler):
    """Handler for journal file system events"""

    def __init__(
        self,
        parser: IJournalParser,
        system_tracker: ISystemTracker,
        repository: IColonizationRepository,
        update_callback: Optional[Callable] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.parser = parser
        self.system_tracker = system_tracker
        self.repository = repository
        self.update_callback = update_callback
        self._processed_files: Set[str] = set()
        # Event loop used to schedule async processing from watchdog threads
        self._loop = loop or asyncio.get_event_loop()

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process journal files
        if not file_path.name.startswith("Journal.") or not file_path.name.endswith(
            ".log"
        ):
            return

        logger.debug(f"Journal file modified: {file_path.name}")
        # Schedule processing on the main event loop from the watchdog thread
        asyncio.run_coroutine_threadsafe(
            self._process_file(file_path),
            self._loop,
        )

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process journal files
        if not file_path.name.startswith("Journal.") or not file_path.name.endswith(
            ".log"
        ):
            return

        logger.info(f"New journal file created: {file_path.name}")
        # Schedule processing on the main event loop from the watchdog thread
        asyncio.run_coroutine_threadsafe(
            self._process_file(file_path),
            self._loop,
        )

    async def _process_file(self, file_path: Path) -> None:
        """
        Process a journal file

        Args:
            file_path: Path to journal file
        """
        try:
            # Parse the file
            events = self.parser.parse_file(file_path)

            if not events:
                return

            # Process each event
            updated_systems: Set[str] = set()

            for event in events:
                # Update system tracker
                if isinstance(event, LocationEvent):
                    self.system_tracker.update_from_location(event)
                elif isinstance(event, FSDJumpEvent):
                    self.system_tracker.update_from_jump(event)
                elif isinstance(event, DockedEvent):
                    self.system_tracker.update_from_docked(event)
                    # Also check if this is a colonization site
                    if (
                        "Colonisation" in event.station_type
                        or "Construction" in event.station_type
                    ):
                        await self._process_docked_at_construction_site(event)
                        updated_systems.add(event.star_system)

                # Process colonization events
                if isinstance(event, ColonizationConstructionDepotEvent):
                    await self._process_construction_depot(event)
                    updated_systems.add(event.system_name)
                elif isinstance(event, ColonizationContributionEvent):
                    await self._process_contribution(event)
                    site = await self.repository.get_site_by_market_id(event.market_id)
                    if site:
                        updated_systems.add(site.system_name)

            # Notify about updates
            if updated_systems and self.update_callback:
                for system_name in updated_systems:
                    await self.update_callback(system_name)

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")

    async def _process_construction_depot(
        self,
        event: ColonizationConstructionDepotEvent,
    ) -> None:
        """
        Process ColonizationConstructionDepot event.

        Notes:
            - Elite can emit many snapshot events while you sit on the
              construction screen. They all share the same MarketID and
              mostly identical data. We treat them as *updates* of a single
              site, not separate sites.
            - Some ColonisationConstructionDepot events omit station/system
              fields; in that case we reuse metadata from any existing site
              with the same market_id (typically created from a Docked event),
              or fall back to the SystemTracker's current system/station.
        """
        # Convert commodities from raw data to Commodity objects
        commodities: list[Commodity] = []
        for comm_data in event.commodities:
            commodity = Commodity(
                name=comm_data.get("Name", ""),
                name_localised=comm_data.get(
                    "Name_Localised", comm_data.get("Name", "")
                ),
                required_amount=comm_data.get("Total", 0),
                provided_amount=comm_data.get("Delivered", 0),
                payment=comm_data.get("Payment", 0),
            )
            commodities.append(commodity)

        # Try to reuse existing site metadata (station/system names) if we have it
        existing_site = await self.repository.get_site_by_market_id(event.market_id)

        # Also fall back to the currently tracked system/station when event fields are missing
        try:
            current_system = self.system_tracker.get_current_system()
        except Exception:
            current_system = None

        try:
            # get_current_station only returns a value when docked
            current_station = self.system_tracker.get_current_station()
        except Exception:
            current_station = None

        # For depot snapshots, prefer any existing site metadata where present.
        # These events can be incomplete (missing station/system), so we do not
        # blindly overwrite good values with placeholders. Renames are handled
        # primarily via Docked events.
        station_name = (
            (existing_site.station_name if existing_site else event.station_name)
            or current_station
            or "Unknown Station"
        )
        station_type = (
            existing_site.station_type if existing_site else event.station_type
        ) or "Unknown"
        system_name = (
            (existing_site.system_name if existing_site else event.system_name)
            or current_system
            or "Unknown System"
        )
        system_address = (
            existing_site.system_address if existing_site else event.system_address
        ) or 0

        # Build the updated site model
        site = ConstructionSite(
            market_id=event.market_id,
            station_name=station_name,
            station_type=station_type,
            system_name=system_name,
            system_address=system_address,
            construction_progress=event.construction_progress,
            construction_complete=event.construction_complete,
            construction_failed=event.construction_failed,
            commodities=commodities,
        )

        # Persist (INSERT OR REPLACE on the same market_id)
        await self.repository.add_construction_site(site)

        logger.info(
            "Updated construction site: %s in %s (%.1f%% complete)",
            site.station_name,
            site.system_name,
            site.construction_progress,
        )

    async def _process_contribution(self, event: ColonizationContributionEvent) -> None:
        """
        Process ColonizationContribution event

        Args:
            event: Contribution event
        """
        await self.repository.update_commodity(
            market_id=event.market_id,
            commodity_name=event.commodity,
            provided_amount=event.total_quantity,
        )

        logger.info(
            f"Contribution recorded: {event.quantity} {event.commodity_localised or event.commodity} "
            f"(total: {event.total_quantity}, credits: {event.credits_received})"
        )

    async def _process_docked_at_construction_site(self, event: DockedEvent) -> None:
        """
        Processes a Docked event that occurs at a construction site.

        If a site already exists for this MarketID but has placeholder
        metadata (e.g. 'Unknown Station' / 'Unknown System'), we upgrade
        that metadata from the Docked event instead of returning early.
        Otherwise this creates a placeholder ConstructionSite.
        """
        existing_site = await self.repository.get_site_by_market_id(event.market_id)
        if existing_site:
            updated = False

            # Always trust the latest Docked metadata; this also allows renamed
            # construction sites to be reflected correctly.
            if event.station_name and event.station_name != existing_site.station_name:
                existing_site.station_name = event.station_name
                updated = True

            if event.station_type and event.station_type != existing_site.station_type:
                existing_site.station_type = event.station_type
                updated = True

            if event.star_system and event.star_system != existing_site.system_name:
                existing_site.system_name = event.star_system
                updated = True

            if (
                event.system_address
                and event.system_address != existing_site.system_address
            ):
                existing_site.system_address = event.system_address
                updated = True

            if updated:
                await self.repository.add_construction_site(existing_site)
                logger.info(
                    "Updated construction site metadata from Docked event: %s in %s",
                    existing_site.station_name,
                    existing_site.system_name,
                )
            return  # Either updated, or already matched the latest metadata

        # No existing site: create placeholder from Docked data
        site = ConstructionSite(
            market_id=event.market_id,
            station_name=event.station_name,
            station_type=event.station_type,
            system_name=event.star_system,
            system_address=event.system_address,
            # We don't have progress or commodity data from a simple Docked event
            construction_progress=0,
            construction_complete=False,
            construction_failed=False,
            commodities=[],
        )
        await self.repository.add_construction_site(site)
        logger.info(
            "Discovered new construction site from Docked event: %s in %s",
            site.station_name,
            site.system_name,
        )


class FileWatcher(IFileWatcher):
    """
    Watches Elite: Dangerous journal directory for changes.
    Uses Observer pattern to notify subscribers.
    """

    def __init__(
        self,
        parser: IJournalParser,
        system_tracker: ISystemTracker,
        repository: IColonizationRepository,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.parser = parser
        self.system_tracker = system_tracker
        self.repository = repository
        self._observer: Optional[Observer] = None
        self._handler: Optional[JournalFileHandler] = None
        self._update_callback: Optional[Callable] = None
        # Event loop used to schedule async processing from watchdog threads
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()

    def set_update_callback(self, callback: Callable) -> None:
        """
        Set callback for when data is updated

        Args:
            callback: Async function to call with system_name when updated
        """
        self._update_callback = callback
        if self._handler:
            self._handler.update_callback = callback

    async def start_watching(self, directory: Path) -> None:
        """
        Start watching directory for changes

        Args:
            directory: Path to journal directory
        """
        if self._observer is not None:
            logger.warning("File watcher already running")
            return

        if not directory.exists():
            logger.error(f"Journal directory does not exist: {directory}")
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

        logger.info(f"Started watching journal directory: {directory}")

        # Process existing files
        await self._process_existing_files(directory)

    async def stop_watching(self) -> None:
        """Stop watching directory"""
        if self._observer is None:
            return

        self._observer.stop()
        self._observer.join()
        self._observer = None
        self._handler = None

        logger.info("Stopped watching journal directory")

    async def _process_existing_files(self, directory: Path) -> None:
        """
        Process existing journal files in directory

        Args:
            directory: Path to journal directory
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
            logger.info(f"Processing journal file: {file_path.name}")
            if self._handler:
                await self._handler._process_file(file_path)
