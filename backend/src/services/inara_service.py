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
_MIN_CALL_INTERVAL_SECONDS = 30.0  # minimum delay between any two Inara calls
_CACHE_TTL = timedelta(minutes=15)

_last_call_at: Optional[datetime] = None
_ban_until: Optional[datetime] = None
_rate_limit_lock = asyncio.Lock()
_system_cache: Dict[str, Tuple[datetime, List[Dict[str, Any]]]] = {}


class InaraService:
    def __init__(self, inara_config: InaraConfig):
        self.config = inara_config
        self.app_name = inara_config.app_name
        self.app_version = "1.0.0"

    async def get_system_colonization_data(self, system_name: str) -> List[Dict[str, Any]]:
        """
        Fetch colonization data for a specific system from Inara.

        This method:
        - Applies a simple global rate limit between requests.
        - Caches responses per system for a short TTL to avoid repeated calls.
        - Detects Inara's own rate-limit responses and backs off for an hour.
        """
        cache_key = system_name.lower()
        now = datetime.utcnow()

        # If we've previously been rate-limited, honor the ban window and avoid hammering the API
        global _ban_until
        if _ban_until is not None and now < _ban_until:
            logger.warning(
                "Skipping Inara request for %s because API access is temporarily revoked until %s",
                system_name,
                _ban_until.isoformat() + "Z",
            )
            cached = _system_cache.get(cache_key)
            if cached:
                cached_at, cached_data = cached
                if now - cached_at < _CACHE_TTL:
                    logger.debug("Returning cached Inara data for %s while ban is active", system_name)
                    return cached_data
            return []

        # Check per-system cache first
        cached = _system_cache.get(cache_key)
        if cached:
            cached_at, cached_data = cached
            if now - cached_at < _CACHE_TTL:
                logger.debug("Returning cached Inara data for %s", system_name)
                return cached_data

        # Resolve application name for Inara:
        # 1) Prefer configured app_name from InaraConfig
        # 2) Fallback to INARA_APP_NAME environment variable
        # 3) Fallback to a sensible default string
        app_name = self.app_name or os.getenv("INARA_APP_NAME") or "EDColonizationAsst"

        header = {
            "appName": app_name,
            "appVersion": self.app_version,
            "isDeveloped": True,  # Use sandbox mode for development
            "APIkey": self.config.api_key,
            "commanderName": self.config.commander_name,
        }

        payload = {
            "header": header,
            "events": [
                {
                    "eventName": "getStarSystemCommunityGoals",
                    "eventTimestamp": datetime.utcnow().isoformat() + "Z",
                    "eventData": {
                        "starSystemName": system_name
                    },
                }
            ],
        }

        try:
            # Global rate limiting to avoid hitting Inara's per-hour caps
            global _last_call_at
            async with _rate_limit_lock:
                if _last_call_at is not None:
                    elapsed = (datetime.utcnow() - _last_call_at).total_seconds()
                    if elapsed < _MIN_CALL_INTERVAL_SECONDS:
                        delay = _MIN_CALL_INTERVAL_SECONDS - elapsed
                        logger.debug(
                            "Rate limiting Inara call for %s, sleeping %.2fs (elapsed %.2fs)",
                            system_name,
                            delay,
                            elapsed,
                        )
                        await asyncio.sleep(delay)
                _last_call_at = datetime.utcnow()

            async with httpx.AsyncClient() as client:
                response = await client.post(INARA_API_URL, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                logger.info("Inara API response for %s: %s", system_name, data)

            # First, check header-level status (covers generic errors including rate limits)
            header_resp = data.get("header", {}) if isinstance(data, dict) else {}
            header_status = header_resp.get("eventStatus")
            header_status_text = header_resp.get("eventStatusText", "")

            if header_status == 400:
                # Inara explicit rate-limit: "Too much requests, slow down, cowboy. ;)"
                ban_duration = timedelta(hours=1)
                _ban_until = datetime.utcnow() + ban_duration
                logger.warning(
                    "Inara API rate limit hit for %s: %s. "
                    "Backing off until %s and caching empty result.",
                    system_name,
                    header_status_text or "Too many requests",
                    _ban_until.isoformat() + "Z",
                )
                _system_cache[cache_key] = (datetime.utcnow(), [])
                return []

            # Then, process per-event responses if present
            events = data.get("events") if isinstance(data, dict) else None
            if not events:
                return []

            # In Inara's schema, the relevant info is in the first event
            event_response = events[0]
            event_status = event_response.get("eventStatus")
            status_text = event_response.get("eventStatusText", "")

            if event_status == 200:
                logger.info("Successfully fetched data from Inara for %s", system_name)
                # The actual data is in the 'eventData' field of the first event
                result = event_response.get("eventData", {}).get("communityGoals", [])
                _system_cache[cache_key] = (datetime.utcnow(), result)
                return result

            if event_status == 204:
                logger.info("No community goals found for %s on Inara.", system_name)
                _system_cache[cache_key] = (datetime.utcnow(), [])
                return []

            logger.error(
                "Inara API returned an error for %s: %s (status: %s)",
                system_name,
                status_text or "Unknown error",
                event_status,
            )
            # On errors (including rate limit), avoid hammering by caching empty for a short TTL
            _system_cache[cache_key] = (datetime.utcnow(), [])
            logger.debug("Full Inara error response for %s: %s", system_name, event_response)
            return []

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error while fetching Inara data for %s: %s", system_name, e)
            return []
        except Exception as e:
            logger.error("An error occurred while fetching Inara data for %s: %s", system_name, e)
            return []


def get_inara_service() -> InaraService:
    """Get an instance of the InaraService"""
    config = get_config()
    return InaraService(inara_config=config.inara)