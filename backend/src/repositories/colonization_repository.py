"""Colonization data repository"""

import asyncio
import json
import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, UTC
from pathlib import Path
from ..models.colonization import ConstructionSite, Commodity
from ..utils.logger import get_logger
from ..utils.runtime import is_frozen

logger = get_logger(__name__)


def _get_db_file() -> Path:
    """
    Determine the location of the colonization SQLite database.

    - In DEV mode (non-frozen): keep the DB next to backend/src as before:
        backend/colonization.db

    - In FROZEN mode (packaged EXE via Nuitka): store the DB under a
      user-local, writable directory so it persists across runs and does
      not live in Nuitka's temporary onefile extraction directory:

        %LOCALAPPDATA%\\EDColonizationAsst\\colonization.db

      If LOCALAPPDATA is not set for any reason, fall back to the user's
      home directory.
    """
    if not is_frozen():
        return Path(__file__).parent.parent / "colonization.db"

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        base = Path(local_appdata) / "EDColonizationAsst"
    else:
        base = Path.home() / ".edcolonizationasst"

    return base / "colonization.db"


DB_FILE = _get_db_file()


class IColonizationRepository(ABC):
    """Interface for colonization data repository"""

    @abstractmethod
    async def add_construction_site(self, site: ConstructionSite) -> None:
        """Add or update construction site data"""
        pass

    @abstractmethod
    async def get_site_by_market_id(self, market_id: int) -> Optional[ConstructionSite]:
        """Get construction site by market ID"""
        pass

    @abstractmethod
    async def get_sites_by_system(self, system_name: str) -> List[ConstructionSite]:
        """Get all construction sites in a system"""
        pass

    @abstractmethod
    async def get_all_systems(self) -> List[str]:
        """Get list of all known systems with construction"""
        pass

    @abstractmethod
    async def get_all_sites(self) -> List[ConstructionSite]:
        """Get all construction sites from the database"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, int]:
        """Get basic statistics about stored construction sites"""
        pass

    @abstractmethod
    async def update_commodity(
        self, market_id: int, commodity_name: str, provided_amount: int
    ) -> None:
        """Update commodity provided amount for a site"""
        pass

    @abstractmethod
    async def clear_all(self) -> None:
        """Clear all data (mainly for testing)"""
        pass


class ColonizationRepository(IColonizationRepository):
    """
    SQLite-based persistent storage for colonization data.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._create_tables()

    def _get_db_connection(self):
        # Ensure the parent directory for the DB exists before connecting,
        # especially in FROZEN mode where we store the DB under
        # %LOCALAPPDATA%\\EDColonizationAsst.
        db_dir = DB_FILE.parent
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error("Failed to create DB directory %s: %s", db_dir, exc)
            # Let sqlite3.connect raise a clearer error below.
        return sqlite3.connect(DB_FILE)

    def _create_tables(self) -> None:
        """Create database tables if they don't exist"""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS construction_sites (
                    market_id INTEGER PRIMARY KEY,
                    station_name TEXT NOT NULL,
                    station_type TEXT,
                    system_name TEXT NOT NULL,
                    system_address INTEGER,
                    construction_progress REAL,
                    construction_complete BOOLEAN,
                    construction_failed BOOLEAN,
                    commodities TEXT,
                    last_updated TEXT
                )
            """
            )
            conn.commit()

    async def add_construction_site(self, site: ConstructionSite) -> None:
        async with self._lock:
            site.last_updated = datetime.now(UTC)
            # Use model_dump (Pydantic v2) instead of deprecated dict()
            commodities_json = json.dumps([c.model_dump() for c in site.commodities])

            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO construction_sites
                    (market_id, station_name, station_type, system_name, system_address,
                    construction_progress, construction_complete, construction_failed,
                    commodities, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        site.market_id,
                        site.station_name,
                        site.station_type,
                        site.system_name,
                        site.system_address,
                        site.construction_progress,
                        site.construction_complete,
                        site.construction_failed,
                        commodities_json,
                        site.last_updated.isoformat(),
                    ),
                )
                conn.commit()
            logger.info(
                "REPOSITORY: Added/updated site %s in %s with data: %s",
                site.station_name,
                site.system_name,
                site.model_dump(),
            )

    async def get_site_by_market_id(self, market_id: int) -> Optional[ConstructionSite]:
        async with self._lock:
            with self._get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM construction_sites WHERE market_id = ?", (market_id,)
                )
                row = cursor.fetchone()
                return self._row_to_site(row) if row else None

    async def get_sites_by_system(self, system_name: str) -> List[ConstructionSite]:
        async with self._lock:
            with self._get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM construction_sites WHERE system_name = ? ORDER BY station_name",
                    (system_name,),
                )
                rows = cursor.fetchall()
                return [self._row_to_site(row) for row in rows if row]

    async def get_all_systems(self) -> List[str]:
        async with self._lock:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT system_name FROM construction_sites ORDER BY system_name"
                )
                rows = cursor.fetchall()
                systems = [row[0] for row in rows]
                logger.info(f"REPOSITORY: Returning {len(systems)} systems: {systems}")
                return systems

    async def get_all_sites(self) -> List[ConstructionSite]:
        async with self._lock:
            with self._get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM construction_sites ORDER BY system_name, station_name"
                )
                rows = cursor.fetchall()
                return [self._row_to_site(row) for row in rows if row]

    async def get_stats(self) -> Dict[str, int]:
        """
        Get basic statistics about stored construction sites.

        Returns:
            Dict[str, int]: {
                "total_systems": number of distinct systems,
                "total_sites": total number of sites,
                "in_progress_sites": sites not yet completed,
                "completed_sites": completed sites,
            }
        """
        sites = await self.get_all_sites()
        total_sites = len(sites)
        completed_sites = sum(1 for s in sites if s.construction_complete)
        in_progress_sites = total_sites - completed_sites
        total_systems = len({s.system_name for s in sites})

        stats = {
            "total_systems": total_systems,
            "total_sites": total_sites,
            "in_progress_sites": in_progress_sites,
            "completed_sites": completed_sites,
        }
        logger.info(f"REPOSITORY: Stats calculated: {stats}")
        return stats

    async def update_commodity(
        self, market_id: int, commodity_name: str, provided_amount: int
    ) -> None:
        """
        Update commodity provided amount for a site.

        Note:
            This method intentionally does NOT acquire self._lock directly,
            because both get_site_by_market_id() and add_construction_site()
            handle their own locking. Acquiring the lock here and then calling
            those methods would result in a deadlock with the non-reentrant
            asyncio.Lock.
        """
        site = await self.get_site_by_market_id(market_id)
        if not site:
            logger.warning(
                f"Cannot update commodity: site with market ID {market_id} not found"
            )
            return

        updated = False
        for commodity in site.commodities:
            if commodity.name == commodity_name:
                commodity.provided_amount = provided_amount
                updated = True
                break

        if updated:
            await self.add_construction_site(site)
            logger.debug(f"Updated {commodity_name} at {site.station_name}")
        else:
            logger.warning(
                f"Commodity {commodity_name} not found at site {site.station_name}"
            )

    async def clear_all(self) -> None:
        async with self._lock:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM construction_sites")
                conn.commit()
            logger.info("Cleared all colonization data")

    def _row_to_site(self, row: sqlite3.Row) -> Optional[ConstructionSite]:
        if not row:
            return None
        commodities_data = json.loads(row["commodities"])
        commodities = [Commodity(**c) for c in commodities_data]
        return ConstructionSite(
            market_id=row["market_id"],
            station_name=row["station_name"],
            station_type=row["station_type"],
            system_name=row["system_name"],
            system_address=row["system_address"],
            construction_progress=row["construction_progress"],
            construction_complete=row["construction_complete"],
            construction_failed=row["construction_failed"],
            commodities=commodities,
            last_updated=datetime.fromisoformat(row["last_updated"]),
        )
