"""Journal event data models"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JournalEvent(BaseModel):
    """Base class for all journal events"""

    timestamp: datetime = Field(description="Event timestamp")
    event: str = Field(description="Event type")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw event data")


class ColonizationConstructionDepotEvent(JournalEvent):
    """ColonizationConstructionDepot event - construction site status"""

    market_id: int = Field(description="Market ID")
    station_name: str = Field(description="Station name")
    station_type: str = Field(description="Station type")
    system_name: str = Field(description="System name")
    system_address: int = Field(description="System address")
    construction_progress: float = Field(description="Construction progress percentage")
    construction_complete: bool = Field(
        default=False, description="Construction complete flag"
    )
    construction_failed: bool = Field(
        default=False, description="Construction failed flag"
    )
    commodities: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of required commodities"
    )


class ColonizationContributionEvent(JournalEvent):
    """ColonizationContribution event - player contribution"""

    market_id: int = Field(description="Market ID")
    commodity: str = Field(description="Commodity name")
    commodity_localised: Optional[str] = Field(
        None, description="Localized commodity name"
    )
    quantity: int = Field(description="Quantity contributed")
    total_quantity: int = Field(description="Total quantity now provided")
    credits_received: int = Field(description="Credits received for contribution")


class LocationEvent(JournalEvent):
    """Location event - current location"""

    star_system: str = Field(description="Star system name")
    system_address: int = Field(description="System address")
    star_pos: List[float] = Field(
        default_factory=list, description="Star position coordinates"
    )
    station_name: Optional[str] = Field(None, description="Station name if docked")
    station_type: Optional[str] = Field(None, description="Station type if docked")
    market_id: Optional[int] = Field(None, description="Market ID if docked")
    docked: bool = Field(default=False, description="Whether docked at station")


class FSDJumpEvent(JournalEvent):
    """FSDJump event - hyperspace jump"""

    star_system: str = Field(description="Destination star system")
    system_address: int = Field(description="System address")
    star_pos: List[float] = Field(
        default_factory=list, description="Star position coordinates"
    )
    jump_dist: float = Field(description="Jump distance in light years")
    fuel_used: float = Field(description="Fuel used")
    fuel_level: float = Field(description="Remaining fuel level")


class DockedEvent(JournalEvent):
    """Docked event - docking at station"""

    station_name: str = Field(description="Station name")
    station_type: str = Field(description="Station type")
    star_system: str = Field(description="Star system name")
    system_address: int = Field(description="System address")
    market_id: int = Field(description="Market ID")
    station_faction: Dict[str, Any] = Field(description="Station faction info")
    station_government: str = Field(description="Station government type")
    station_economy: str = Field(description="Station economy type")
    station_economies: List[Dict[str, Any]] = Field(description="Station economies")


class CommanderEvent(JournalEvent):
    """Commander event - commander information"""

    name: str = Field(description="Commander name")
    fid: str = Field(description="Frontier ID")
