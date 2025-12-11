"""API request and response models"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from .colonization import ConstructionSite, SystemColonizationData, CommodityAggregate


class SystemResponse(BaseModel):
    """Response model for system colonization data"""

    system_name: str = Field(description="Star system name")
    construction_sites: List[ConstructionSite] = Field(
        description="Construction sites in system"
    )
    total_sites: int = Field(description="Total number of sites")
    completed_sites: int = Field(description="Number of completed sites")
    in_progress_sites: int = Field(description="Number of in-progress sites")
    completion_percentage: float = Field(description="Overall completion percentage")


class SiteResponse(BaseModel):
    """Response model for a single construction site"""

    site: ConstructionSite = Field(description="Construction site data")


class SystemListResponse(BaseModel):
    """Response model for list of systems"""

    systems: List[str] = Field(description="List of system names with construction")


class SiteListResponse(BaseModel):
    """Response model for a list of construction sites, categorized by status."""

    in_progress_sites: List[ConstructionSite] = Field(
        description="List of sites currently under construction"
    )
    completed_sites: List[ConstructionSite] = Field(
        description="List of completed construction sites"
    )


class CommodityAggregateResponse(BaseModel):
    """Response model for aggregated commodity data"""

    commodities: List[CommodityAggregate] = Field(
        description="Aggregated commodity data"
    )


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str = Field(description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(description="HTTP status code")


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(default="healthy", description="Service status")
    version: str = Field(description="Application version")
    journal_directory: str = Field(description="Configured journal directory")
    journal_accessible: bool = Field(
        description="Whether journal directory is accessible"
    )


class WebSocketMessageType(str, Enum):
    """WebSocket message types"""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    UPDATE = "update"
    SYSTEM_CHANGED = "system_changed"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WebSocketMessage(BaseModel):
    """WebSocket message model"""

    type: WebSocketMessageType = Field(description="Message type")
    system_name: Optional[str] = Field(
        None, description="System name for subscribe/update"
    )
    data: Optional[Dict[str, Any]] = Field(None, description="Message data")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    error: Optional[str] = Field(None, description="Error message if type is error")


class SubscribeMessage(BaseModel):
    """Subscribe to system updates"""

    type: WebSocketMessageType = Field(default=WebSocketMessageType.SUBSCRIBE)
    system_name: str = Field(description="System name to subscribe to")


class UnsubscribeMessage(BaseModel):
    """Unsubscribe from system updates"""

    type: WebSocketMessageType = Field(default=WebSocketMessageType.UNSUBSCRIBE)
    system_name: str = Field(description="System name to unsubscribe from")


class AppSettings(BaseModel):
    """Application settings model"""

    journal_directory: str
    inara_api_key: str | None
    inara_commander_name: str | None
