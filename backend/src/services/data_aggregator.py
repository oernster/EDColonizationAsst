"""Data aggregation service"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from collections import defaultdict
from ..models.colonization import (
    ConstructionSite,
    SystemColonizationData,
    CommodityAggregate
)
from ..repositories.colonization_repository import IColonizationRepository
from .inara_service import InaraService, get_inara_service
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IDataAggregator(ABC):
    """Interface for data aggregation"""
    
    @abstractmethod
    async def aggregate_by_system(self, system_name: str) -> SystemColonizationData:
        """Aggregate all construction sites in a system"""
        pass
    
    @abstractmethod
    async def aggregate_commodities(
        self, 
        sites: List[ConstructionSite]
    ) -> List[CommodityAggregate]:
        """Aggregate commodities across multiple sites"""
        pass


class DataAggregator(IDataAggregator):
    """
    Aggregates colonization data.
    Follows Open/Closed Principle - extensible for new aggregation types.

    Strategy:
      - INCOMPLETE sites come from LOCAL JOURNAL data.
      - COMPLETED sites may come from INARA (or local if available).
    Local data is never downgraded by Inara; Inara can only:
      - mark a local site as completed, or
      - add a completed site that is missing locally.
    """
    
    def __init__(self, repository: IColonizationRepository) -> None:
        self._repository = repository
        self._inara_service = get_inara_service()
    
    async def aggregate_by_system(self, system_name: str) -> SystemColonizationData:
        """
        Aggregate all construction sites in a system.
        
        Incomplete progress is taken from local journal data.
        Completion status may be upgraded using Inara.
        
        Args:
            system_name: Star system name
            
        Returns:
            Aggregated system colonization data
        """
        # Get local data from journal files
        local_sites = await self._repository.get_sites_by_system(system_name)
        
        # Get data from Inara
        try:
            inara_sites_data = await self._inara_service.get_system_colonization_data(system_name)
            inara_sites = [self._transform_inara_data(site_data) for site_data in inara_sites_data]
        except Exception as e:
            logger.error(f"Error fetching or transforming Inara data: {e}")
            inara_sites = []
        
        # If Inara has no data, just return the local data
        if not inara_sites:
            return SystemColonizationData(
                system_name=system_name,
                construction_sites=sorted(local_sites, key=lambda s: s.station_name)
            )

        # Start with all local sites
        merged_sites: Dict[int, ConstructionSite] = {site.market_id: site for site in local_sites}

        # Index Inara sites by market_id
        inara_by_id: Dict[int, ConstructionSite] = {
            site.market_id: site for site in inara_sites
        }

        # 1) Upgrade local sites to completed if Inara says they are completed.
        for market_id, local_site in merged_sites.items():
            inara_site = inara_by_id.get(market_id)
            if inara_site and inara_site.construction_complete and not local_site.construction_complete:
                logger.info(
                    "Marking site %s in %s (market_id=%s) as completed from Inara data.",
                    local_site.station_name,
                    local_site.system_name,
                    local_site.market_id,
                )
                # Upgrade completion status from Inara
                local_site.construction_complete = True
                local_site.construction_failed = inara_site.construction_failed
                # Prefer the higher progress value
                local_site.construction_progress = max(
                    local_site.construction_progress,
                    inara_site.construction_progress,
                )
                # Optionally ensure commodities look complete where possible
                for comm in local_site.commodities:
                    if comm.required_amount > 0 and comm.provided_amount < comm.required_amount:
                        comm.provided_amount = comm.required_amount
                await self._repository.add_construction_site(local_site)

        # 2) Add completed sites that only exist in Inara (no local data at all).
        for market_id, inara_site in inara_by_id.items():
            if inara_site.construction_complete and market_id not in merged_sites:
                logger.info(
                    "Adding completed site %s in %s (market_id=%s) from Inara only.",
                    inara_site.station_name,
                    inara_site.system_name,
                    inara_site.market_id,
                )
                merged_sites[market_id] = inara_site
                await self._repository.add_construction_site(inara_site)

        # NOTE:
        # We deliberately do NOT pull in INCOMPLETE sites from Inara if there is
        # no local data. This avoids phantom in-progress stations that the
        # commander has never seen in their own journals.

        return SystemColonizationData(
            system_name=system_name,
            construction_sites=sorted(merged_sites.values(), key=lambda s: s.station_name)
        )
    
    async def aggregate_commodities(
        self, 
        sites: List[ConstructionSite]
    ) -> List[CommodityAggregate]:
        """
        Aggregate commodities across multiple sites
        
        Args:
            sites: List of construction sites
            
        Returns:
            List of aggregated commodity data
        """
        # Dictionary to accumulate commodity data
        # Key: commodity name, Value: aggregation data
        commodity_data: Dict[str, Dict] = defaultdict(lambda: {
            "name": "",
            "name_localised": "",
            "total_required": 0,
            "total_provided": 0,
            "sites": [],
            "payments": []
        })
        
        # Aggregate data from all sites
        for site in sites:
            for commodity in site.commodities:
                data = commodity_data[commodity.name]
                
                # Set names (first occurrence)
                if not data["name"]:
                    data["name"] = commodity.name
                    data["name_localised"] = commodity.name_localised
                
                # Accumulate amounts
                data["total_required"] += commodity.required_amount
                data["total_provided"] += commodity.provided_amount
                
                # Track which sites need this commodity
                if commodity.remaining_amount > 0:
                    data["sites"].append(site.station_name)
                
                # Collect payments for averaging
                data["payments"].append(commodity.payment)
        
        # Convert to CommodityAggregate objects
        aggregates: List[CommodityAggregate] = []
        
        for commodity_name, data in commodity_data.items():
            # Calculate average payment
            avg_payment = (
                sum(data["payments"]) / len(data["payments"])
                if data["payments"] else 0.0
            )
            
            aggregate = CommodityAggregate(
                commodity_name=data["name"],
                commodity_name_localised=data["name_localised"],
                total_required=data["total_required"],
                total_provided=data["total_provided"],
                sites_requiring=data["sites"],
                average_payment=avg_payment
            )
            
            aggregates.append(aggregate)
        
        # Sort by total remaining (most needed first)
        aggregates.sort(key=lambda x: x.total_remaining, reverse=True)
        
        return aggregates
    
    async def get_system_summary(self, system_name: str) -> Dict[str, any]:
        """
        Get a summary of colonization progress in a system
        
        Args:
            system_name: Star system name
            
        Returns:
            Dictionary with summary statistics
        """
        system_data = await self.aggregate_by_system(system_name)
        commodities = await self.aggregate_commodities(system_data.construction_sites)
        
        # Calculate total commodities needed
        total_needed = sum(c.total_remaining for c in commodities)
        
        # Find most needed commodity
        most_needed = None
        if commodities:
            most_needed = {
                "name": commodities[0].commodity_name_localised,
                "amount": commodities[0].total_remaining
            }
        
        return {
            "system_name": system_name,
            "total_sites": system_data.total_sites,
            "completed_sites": system_data.completed_sites,
            "in_progress_sites": system_data.in_progress_sites,
            "completion_percentage": system_data.completion_percentage,
            "total_commodities_needed": total_needed,
            "unique_commodities": len(commodities),
            "most_needed_commodity": most_needed
        }

    def _transform_inara_data(self, inara_site_data: Dict[str, Any]) -> ConstructionSite:
        """
        Transforms Inara API data into a ConstructionSite model.
        """
        from ..models.colonization import DataSource, Commodity
        
        commodities = []
        for comm in inara_site_data.get("commodities", []):
            commodities.append(Commodity(
                name=comm.get("name", ""),
                name_localised=comm.get("name_localised", ""),
                required_amount=comm.get("required", 0),
                provided_amount=comm.get("provided", 0),
                payment=comm.get("payment", 0),
            ))

        return ConstructionSite(
            market_id=inara_site_data.get("marketId", 0),
            station_name=inara_site_data.get("stationName", "Unknown"),
            station_type=inara_site_data.get("stationType", "Unknown"),
            system_name=inara_site_data.get("systemName", "Unknown"),
            system_address=inara_site_data.get("systemAddress", 0),
            construction_progress=inara_site_data.get("progress", 0.0),
            construction_complete=inara_site_data.get("isCompleted", False),
            construction_failed=inara_site_data.get("isFailed", False),
            commodities=commodities,
            last_source=DataSource.INARA,
        )