"""Journal file parser service"""
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..models.journal_events import (
    JournalEvent,
    ColonizationConstructionDepotEvent,
    ColonizationContributionEvent,
    LocationEvent,
    FSDJumpEvent,
    DockedEvent,
    CommanderEvent
)
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IJournalParser(ABC):
    """Interface for journal file parser"""
    
    @abstractmethod
    def parse_file(self, file_path: Path) -> List[JournalEvent]:
        """Parse a journal file and return list of events"""
        pass
    
    @abstractmethod
    def parse_line(self, line: str) -> Optional[JournalEvent]:
        """Parse a single line from journal file"""
        pass


class JournalParser(IJournalParser):
    """
    Parses Elite: Dangerous journal files.
    Follows Single Responsibility Principle - only responsible for parsing.
    """
    
    # Event types we care about
    RELEVANT_EVENTS = {
        "ColonizationConstructionDepot",
        "ColonizationContribution",
        "Location",
        "FSDJump",
        "Docked",
        "Commander"
    }
    
    def parse_file(self, file_path: Path) -> List[JournalEvent]:
        """
        Parse a journal file and return list of relevant events
        
        Args:
            file_path: Path to journal file
            
        Returns:
            List of parsed journal events
        """
        events: List[JournalEvent] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        event = self.parse_line(line)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse line {line_num} in {file_path.name}: {e}"
                        )
                        continue
            
            logger.info(f"Parsed {len(events)} relevant events from {file_path.name}")
            return events
            
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            return []
    
    def parse_line(self, line: str) -> Optional[JournalEvent]:
        """
        Parse a single line from journal file
        
        Args:
            line: JSON line from journal file
            
        Returns:
            Parsed event or None if not relevant
        """
        try:
            data = json.loads(line)
            event_type = data.get("event")
            
            if event_type not in self.RELEVANT_EVENTS:
                return None
            
            # Parse timestamp
            timestamp_str = data.get("timestamp", "")
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Route to appropriate parser
            if event_type == "ColonizationConstructionDepot":
                return self._parse_construction_depot(data, timestamp)
            elif event_type == "ColonizationContribution":
                return self._parse_contribution(data, timestamp)
            elif event_type == "Location":
                return self._parse_location(data, timestamp)
            elif event_type == "FSDJump":
                return self._parse_fsd_jump(data, timestamp)
            elif event_type == "Docked":
                return self._parse_docked(data, timestamp)
            elif event_type == "Commander":
                return self._parse_commander(data, timestamp)
            
            return None
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing line: {e}")
            return None
    
    def _parse_construction_depot(
        self, 
        data: Dict[str, Any], 
        timestamp: datetime
    ) -> ColonizationConstructionDepotEvent:
       """Parse ColonizationConstructionDepot event"""
       logger.info(f"Parsing ColonizationConstructionDepotEvent: {data}")
       return ColonizationConstructionDepotEvent(
           timestamp=timestamp,
           event=data["event"],
            market_id=data["MarketID"],
            station_name=data["StationName"],
            station_type=data["StationType"],
            system_name=data["StarSystem"],
            system_address=data["SystemAddress"],
            construction_progress=data.get("ConstructionProgress", 0.0),
            construction_complete=data.get("ConstructionComplete", False),
            construction_failed=data.get("ConstructionFailed", False),
            commodities=data.get("Commodities", []),
            raw_data=data
        )
    
    def _parse_contribution(
        self, 
        data: Dict[str, Any], 
        timestamp: datetime
    ) -> ColonizationContributionEvent:
       """Parse ColonizationContribution event"""
       logger.info(f"Parsing ColonizationContributionEvent: {data}")
       return ColonizationContributionEvent(
           timestamp=timestamp,
           event=data["event"],
            market_id=data["MarketID"],
            commodity=data["Commodity"],
            commodity_localised=data.get("Commodity_Localised"),
            quantity=data["Quantity"],
            total_quantity=data["TotalQuantity"],
            credits_received=data.get("CreditsReceived", 0),
            raw_data=data
        )
    
    def _parse_location(
        self, 
        data: Dict[str, Any], 
        timestamp: datetime
    ) -> LocationEvent:
        """Parse Location event"""
        return LocationEvent(
            timestamp=timestamp,
            event=data["event"],
            star_system=data["StarSystem"],
            system_address=data["SystemAddress"],
            star_pos=data.get("StarPos", []),
            station_name=data.get("StationName"),
            station_type=data.get("StationType"),
            market_id=data.get("MarketID"),
            docked=data.get("Docked", False),
            raw_data=data
        )
    
    def _parse_fsd_jump(
        self, 
        data: Dict[str, Any], 
        timestamp: datetime
    ) -> FSDJumpEvent:
        """Parse FSDJump event"""
        return FSDJumpEvent(
            timestamp=timestamp,
            event=data["event"],
            star_system=data["StarSystem"],
            system_address=data["SystemAddress"],
            star_pos=data.get("StarPos", []),
            jump_dist=data.get("JumpDist", 0.0),
            fuel_used=data.get("FuelUsed", 0.0),
            fuel_level=data.get("FuelLevel", 0.0),
            raw_data=data
        )
    
    def _parse_docked(
        self, 
        data: Dict[str, Any], 
        timestamp: datetime
    ) -> DockedEvent:
        """Parse Docked event"""
        return DockedEvent(
            timestamp=timestamp,
            event=data["event"],
            station_name=data["StationName"],
            station_type=data["StationType"],
            star_system=data["StarSystem"],
            system_address=data["SystemAddress"],
            market_id=data["MarketID"],
            station_faction=data.get("StationFaction"),
            station_government=data.get("StationGovernment"),
            station_economy=data.get("StationEconomy"),
            station_economies=data.get("StationEconomies", []),
            raw_data=data
        )

    def _parse_commander(
        self,
        data: Dict[str, Any],
        timestamp: datetime
    ) -> CommanderEvent:
        """Parse Commander event"""
        return CommanderEvent(
            timestamp=timestamp,
            event=data["event"],
            name=data["Name"],
            fid=data["FID"],
            raw_data=data
        )