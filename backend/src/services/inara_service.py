"""Service for fetching data from the Inara.cz API"""
import os
import httpx
from datetime import datetime
from typing import List, Dict, Any
from ..config import get_config, InaraConfig
from ..utils.logger import get_logger

logger = get_logger(__name__)

INARA_API_URL = "https://inara.cz/inapi/v1/"

class InaraService:
    def __init__(self, inara_config: InaraConfig):
        self.config = inara_config
        self.app_name = inara_config.app_name
        self.app_version = "1.0.0"

    async def get_system_colonization_data(self, system_name: str) -> List[Dict[str, Any]]:
        """
        Fetch colonization data for a specific system from Inara.
        """
        header = {
            "appName": os.getenv("INARA_APP_NAME", ""),
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
                    }
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(INARA_API_URL, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Inara API response for {system_name}: {data}")

                if "events" in data and data["events"]:
                    event_response = data["events"]
                    event_status = event_response.get("eventStatus")
                    if event_status == 200:
                        logger.info(f"Successfully fetched data from Inara for {system_name}")
                        # The actual data is in the 'eventData' field of the first event
                        return event_response.get("eventData", {}).get("communityGoals", [])
                    elif event_status == 204:
                        logger.info(f"No community goals found for {system_name} on Inara.")
                        return []
                    else:
                        status_text = event_response.get('eventStatusText', 'Unknown error')
                        logger.error(f"Inara API returned an error for {system_name}: {status_text} (status: {event_status})")
                        # Also log the full event response for detailed debugging
                        logger.debug(f"Full Inara error response: {event_response}")
                        return []
                return []

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while fetching Inara data for {system_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"An error occurred while fetching Inara data for {system_name}: {e}")
            return []

def get_inara_service() -> InaraService:
    """Get an instance of the InaraService"""
    config = get_config()
    return InaraService(inara_config=config.inara)