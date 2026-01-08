"""Service for fetching data from the Inara.cz API"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import httpx

from ..config import get_config, InaraConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

INARA_API_URL = "https://inara.cz/inapi/v1/"

# Simple in-process rate limiting and per-system caching for Inara API calls
# NOTE: These limits are intentionally conservative to avoid Inara API bans.
# Community guidance is ~2 requests/min; 35s keeps us safely under that.
_MIN_CALL_INTERVAL_SECONDS = 35.0  # minimum delay between any two Inara calls
_CACHE_TTL = timedelta(minutes=15)

_last_call_at: Optional[datetime] = None
_ban_until: Optional[datetime] = None
_rate_limit_lock = asyncio.Lock()
_system_cache: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}


class InaraService:
    def __init__(self, inara_config: InaraConfig):
        self.config = inara_config
        self.app_name = inara_config.app_name
        # Keep this aligned with the app version used elsewhere.
        # Canonical version is loaded from the top-level VERSION file.
        from .. import __version__

        self.app_version = __version__

    async def get_system_colonization_data(
        self, system_name: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch colonization-related data for a specific system from Inara.

        NOTE:
        There is currently no confirmed INAPI v1 event that exposes the
        construction/colonization data this application needs (stations or
        planetary bases under construction, required commodities, etc.).
        Previous attempts incorrectly used community-goal events, which are
        unrelated to this feature and caused confusing errors and logs.

        Until a proper colonization-related Inara event is identified, this
        method intentionally performs **no HTTP requests** and always returns
        an empty list so that the rest of the application relies solely on
        local journal data for colonization tracking.
        """
        logger.debug(
            "Inara colonization integration not implemented for system %s; "
            "returning no remote colonization data.",
            system_name,
        )
        return []


def get_inara_service() -> InaraService:
    """Get an instance of the InaraService"""
    config = get_config()
    return InaraService(inara_config=config.inara)
