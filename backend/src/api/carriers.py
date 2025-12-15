"""API routes for Fleet carriers.

These endpoints expose a derived view of fleet carrier state to power the
Frontend Fleet carriers tab. Data is reconstructed on demand from the
latest Elite: Dangerous journal file; no additional persistence is used.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, HTTPException

from ..models.api_models import (
    CarrierStateResponse,
    CurrentCarrierResponse,
    MyCarriersResponse,
)
from ..models.carriers import (
    CarrierIdentity,
    CarrierRole,
    CarrierState,
    CarrierCargoItem,
    CarrierOrder,
    CarrierOrderType,
)
from ..models.journal_events import (
    CarrierLocationEvent,
    CarrierStatsEvent,
    CarrierTradeOrderEvent,
    DockedEvent,
    JournalEvent,
)
from ..services.journal_parser import JournalParser
from ..utils.journal import get_journal_directory, get_latest_journal_file
from ..utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/carriers", tags=["carriers"])


def _load_latest_journal_events() -> Tuple[List[JournalEvent], Optional[str]]:
    """Parse the latest journal file and return all relevant events.

    Returns:
        (events, file_path_str) where file_path_str is None if there is
        no journal file available.
    """
    try:
        journal_dir = get_journal_directory()
        latest_file = get_latest_journal_file(journal_dir)
    except FileNotFoundError:
        logger.warning("Journal directory not found while querying carrier state.")
        return [], None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error resolving journal directory: %s", exc)
        return [], None

    if not latest_file:
        logger.info("No Journal.*.log files found when querying carrier state.")
        return [], None

    parser = JournalParser()
    events = parser.parse_file(latest_file)
    return events, str(latest_file)


def _find_latest_docked_carrier(events: List[JournalEvent]) -> Optional[DockedEvent]:
    """Return the most recent DockedEvent at a fleet carrier, if any."""
    for event in reversed(events):
        if isinstance(event, DockedEvent) and event.station_type == "FleetCarrier":
            return event
    return None


def _find_latest_carrier_stats_for_id(
    events: List[JournalEvent],
    carrier_id: int,
) -> Optional[CarrierStatsEvent]:
    """Return the latest CarrierStatsEvent for the given carrier id, if any."""
    for event in reversed(events):
        if isinstance(event, CarrierStatsEvent) and event.carrier_id == carrier_id:
            return event
    return None


def _find_latest_carrier_location_for_id(
    events: List[JournalEvent],
    carrier_id: int,
) -> Optional[CarrierLocationEvent]:
    """Return the latest CarrierLocationEvent for the given carrier id, if any."""
    for event in reversed(events):
        if isinstance(event, CarrierLocationEvent) and event.carrier_id == carrier_id:
            return event
    return None


def _build_identity_from_journal(
    docked_event: DockedEvent,
    stats: Optional[CarrierStatsEvent],
    location: Optional[CarrierLocationEvent],
) -> CarrierIdentity:
    """Construct a CarrierIdentity from journal events.

    Notes
    -----
    - CarrierStats is emitted for the commander's own carrier.
    - Current journal data does not reliably distinguish an official
      squadron carrier from a personal carrier with squadron docking
      access, so we do *not* infer CarrierRole.SQUADRON here.
    """

    carrier_unique_id = docked_event.market_id
    last_seen_system = (
        location.star_system
        if location is not None
        else docked_event.star_system
    )
    last_seen_timestamp = (
        stats.timestamp
        if stats is not None and stats.timestamp is not None
        else docked_event.timestamp
    )

    # Determine role heuristically.
    role = CarrierRole.OTHER
    if stats is not None:
        # Treat any carrier for which we see CarrierStats as OWN.
        # We intentionally do *not* infer a dedicated squadron carrier
        # from the DockingAccess field, because that only controls who
        # may dock there and does not identify the squadron's official
        # carrier.
        role = CarrierRole.OWN

    # Docking access and services, when available.
    docking_access: Optional[str] = None
    services: Optional[list[str]] = None

    # Start with any activated crew roles from CarrierStats.Crew, which
    # represent the installed/active carrier services (e.g. Exploration,
    # Outfitting, PioneerSupplies, VistaGenomics, Bartender, etc.).
    service_names_set: set[str] = set()
    raw_services = None

    if stats is not None:
        docking_access = stats.raw_data.get("DockingAccess")

        crew_list = stats.raw_data.get("Crew") or []
        if isinstance(crew_list, list):
            for crew in crew_list:
                if not isinstance(crew, dict):
                    continue
                if not crew.get("Activated"):
                    continue
                crew_role = crew.get("CrewRole")
                if not isinstance(crew_role, str):
                    continue
                role_lower = crew_role.lower()
                # Ignore non-service roles such as Captain.
                if role_lower == "captain":
                    continue
                service_names_set.add(role_lower)

        # Some journal variants may also expose services directly on CarrierStats.
        raw_services = (
            stats.raw_data.get("Services")
            or stats.raw_data.get("StationServices")
        )

    # Fall back to StationServices on the Docked event if CarrierStats
    # does not expose a services list explicitly.
    if raw_services is None:
        raw_services = docked_event.raw_data.get("StationServices")

    if isinstance(raw_services, list):
        for item in raw_services:
            if isinstance(item, str):
                service_names_set.add(item.lower())
            elif isinstance(item, dict):
                name = item.get("Name") or item.get("name")
                if isinstance(name, str):
                    service_names_set.add(name.lower())

    if service_names_set:
        # Sort for stable output.
        services = sorted(service_names_set)

    # Choose the most descriptive name/callsign we have.
    name = (
        stats.name
        if stats is not None and stats.name
        else docked_event.station_name
    )
    callsign = stats.callsign if stats is not None else None

    return CarrierIdentity(
        carrier_id=carrier_unique_id,
        market_id=docked_event.market_id,
        name=name,
        callsign=callsign,
        role=role,
        docking_access=docking_access,
        last_seen_system=last_seen_system,
        last_seen_timestamp=last_seen_timestamp,
        services=services,
    )


def _build_orders_for_carrier(
    events: List[JournalEvent],
    carrier_id: int,
) -> Tuple[List[CarrierCargoItem], List[CarrierOrder], List[CarrierOrder]]:
    """Build cargo, buy and sell orders for a given carrier from CarrierTradeOrder events.

    The journal events look like (examples from your logs):

        {
          "timestamp":"2025-12-15T11:17:37Z",
          "event":"CarrierTradeOrder",
          "CarrierID":3700569600,
          "CarrierType":"FleetCarrier",
          "BlackMarket":false,
          "Commodity":"titanium",
          "SaleOrder":23,
          "Price":4446
        }

        {
          "timestamp":"2025-12-15T11:20:15Z",
          "event":"CarrierTradeOrder",
          "CarrierID":3700569600,
          "CarrierType":"FleetCarrier",
          "BlackMarket":false,
          "Commodity":"tritium",
          "PurchaseOrder":1,
          "Price":51294
        }

        {
          "timestamp":"2025-12-15T11:20:20Z",
          "event":"CarrierTradeOrder",
          "CarrierID":3700569600,
          "CarrierType":"FleetCarrier",
          "BlackMarket":false,
          "Commodity":"tritium",
          "CancelTrade":true
        }

    We infer order_type via the presence of PurchaseOrder vs SaleOrder.

    Semantics
    ---------
    - Orders are modelled as the *latest known state per commodity*, not as
      a historical list. Subsequent CarrierTradeOrder events for the same
      commodity overwrite earlier ones.
    - CancelTrade events remove any existing buy/sell order and associated
      cargo entry for that commodity.
    - For SELL orders we treat the SaleOrder quantity as a proxy for
      "available stock" for that commodity on the carrier.
    """
    # Latest buy/sell order per commodity.
    buy_orders_by_commodity: dict[str, CarrierOrder] = {}
    sell_orders_by_commodity: dict[str, CarrierOrder] = {}

    # Aggregate cargo stock per commodity based on SELL orders. This does not
    # represent the full physical cargo hold, but it provides a useful view of
    # "stock assigned to the market" for each commodity.
    cargo_by_commodity: dict[str, dict[str, object]] = {}

    for event in events:
        if not isinstance(event, CarrierTradeOrderEvent):
            continue
        if event.carrier_id != carrier_id:
            continue

        commodity_key = event.commodity or ""

        # Explicit cancel: clear any existing orders and cargo entry.
        if event.raw_data.get("CancelTrade"):
            buy_orders_by_commodity.pop(commodity_key, None)
            sell_orders_by_commodity.pop(commodity_key, None)
            cargo_by_commodity.pop(commodity_key, None)
            continue

        # Determine order type
        order_type: Optional[CarrierOrderType] = None
        if event.sale_order > 0:
            order_type = CarrierOrderType.SELL
        elif event.purchase_order > 0:
            order_type = CarrierOrderType.BUY
        else:
            # Neither sale nor purchase order (and no CancelTrade): ignore.
            continue

        # Original and remaining amounts: prefer explicit Outstanding when present.
        if order_type == CarrierOrderType.SELL:
            original_amount = event.sale_order or event.outstanding
        else:
            original_amount = event.purchase_order or event.outstanding

        remaining_amount = event.outstanding if event.outstanding >= 0 else original_amount

        order = CarrierOrder(
            order_type=order_type,
            commodity_name=event.commodity,
            commodity_name_localised=event.commodity_localised or event.commodity,
            price=event.price,
            original_amount=max(original_amount, 0),
            remaining_amount=max(remaining_amount, 0),
            stock=event.stock if event.stock >= 0 else None,
        )

        if order_type == CarrierOrderType.SELL:
            # Latest SELL order wins for this commodity.
            sell_orders_by_commodity[commodity_key] = order

            # Reflect SELL orders into a simple cargo view (latest snapshot).
            sale_qty = max(event.sale_order, 0)
            cargo_by_commodity[commodity_key] = {
                "commodity_name": event.commodity,
                "commodity_name_localised": event.commodity_localised or event.commodity,
                "stock": sale_qty,
                "reserved": 0,
                "capacity": None,
            }
        else:
            # Latest BUY order wins for this commodity.
            buy_orders_by_commodity[commodity_key] = order

    # Convert cargo map into CarrierCargoItem list
    cargo_items: List[CarrierCargoItem] = []
    for data in cargo_by_commodity.values():
        cargo_items.append(
            CarrierCargoItem(
                commodity_name=data["commodity_name"],  # type: ignore[arg-type]
                commodity_name_localised=data["commodity_name_localised"],  # type: ignore[arg-type]
                stock=int(data["stock"]),  # type: ignore[arg-type]
                reserved=int(data["reserved"]),  # type: ignore[arg-type]
                capacity=data["capacity"],  # type: ignore[arg-type]
            )
        )

    buy_orders = list(buy_orders_by_commodity.values())
    sell_orders = list(sell_orders_by_commodity.values())

    return cargo_items, buy_orders, sell_orders


@router.get("/current", response_model=CurrentCarrierResponse)
async def get_current_carrier() -> CurrentCarrierResponse:
    """Return the carrier (if any) the commander is currently docked at.

    This is derived purely from the latest journal file by finding the
    most recent Docked event whose StationType is FleetCarrier and
    enriching it with CarrierStats/CarrierLocation where available.
    """
    events, _ = _load_latest_journal_events()
    if not events:
        # No journal data; report that we are not docked at a carrier.
        return CurrentCarrierResponse(docked_at_carrier=False, carrier=None)

    docked_carrier = _find_latest_docked_carrier(events)
    if docked_carrier is None:
        return CurrentCarrierResponse(docked_at_carrier=False, carrier=None)

    stats = _find_latest_carrier_stats_for_id(events, docked_carrier.market_id)
    location = _find_latest_carrier_location_for_id(events, docked_carrier.market_id)

    identity = _build_identity_from_journal(docked_carrier, stats, location)

    return CurrentCarrierResponse(docked_at_carrier=True, carrier=identity)


@router.get("/current/state", response_model=CarrierStateResponse)
async def get_current_carrier_state() -> CarrierStateResponse:
    """Return a reconstructed snapshot of the currently docked carrier.
 
    The snapshot currently includes:
      - Identity (name, callsign, role, last-seen system)
      - A best-effort cargo view derived from CarrierTradeOrder SELL orders
      - Buy and sell orders derived from CarrierTradeOrder events
      - Total cargo tonnage from CarrierStats.SpaceUsage.Cargo when available
 
    As more carrier-specific events become available (e.g. explicit cargo
    storage snapshots), this view can be refined.
    """
    events, _ = _load_latest_journal_events()
    if not events:
        raise HTTPException(status_code=404, detail="No journal data available")
 
    docked_carrier = _find_latest_docked_carrier(events)
    if docked_carrier is None:
        raise HTTPException(
            status_code=404,
            detail="Commander is not currently docked at a fleet carrier",
        )
 
    stats = _find_latest_carrier_stats_for_id(events, docked_carrier.market_id)
    location = _find_latest_carrier_location_for_id(events, docked_carrier.market_id)
    identity = _build_identity_from_journal(docked_carrier, stats, location)
 
    # Build cargo and buy/sell orders from CarrierTradeOrder events.
    cargo, buy_orders, sell_orders = _build_orders_for_carrier(
        events, docked_carrier.market_id
    )
 
    # Derive cargo and capacity metrics from CarrierStats.SpaceUsage when present.
    total_cargo_tonnage: Optional[int] = None
    total_capacity_tonnage: Optional[int] = None
    free_space_tonnage: Optional[int] = None

    if stats is not None:
        try:
            space_usage = stats.raw_data.get("SpaceUsage") or {}
            cargo_tonnage = space_usage.get("Cargo")
            total_capacity = space_usage.get("TotalCapacity")
            free_space = space_usage.get("FreeSpace")

            if isinstance(cargo_tonnage, (int, float)):
                total_cargo_tonnage = int(round(cargo_tonnage))
            if isinstance(total_capacity, (int, float)):
                total_capacity_tonnage = int(round(total_capacity))
            if isinstance(free_space, (int, float)):
                free_space_tonnage = int(round(free_space))
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to derive cargo/capacity metrics from CarrierStats",
                exc_info=True,
            )

    # Use the most recent of stats/location/docked timestamps as snapshot time.
    snapshot_time = docked_carrier.timestamp
    if stats is not None and stats.timestamp > snapshot_time:
        snapshot_time = stats.timestamp
    if location is not None and location.timestamp > snapshot_time:
        snapshot_time = location.timestamp

    state = CarrierState(
        identity=identity,
        cargo=cargo,
        total_cargo_tonnage=total_cargo_tonnage,
        total_capacity_tonnage=total_capacity_tonnage,
        free_space_tonnage=free_space_tonnage,
        buy_orders=buy_orders,
        sell_orders=sell_orders,
        snapshot_time=snapshot_time,
    )
    return CarrierStateResponse(carrier=state)


@router.get("/mine", response_model=MyCarriersResponse)
async def get_my_carriers() -> MyCarriersResponse:
    """Return a list of the commander's own and squadron carriers.

    This endpoint walks the latest journal file and looks for CarrierStats
    and CarrierLocation events, grouping by carrier id. It does *not* try
    to discover arbitrary third-party carriers beyond what the journal
    exposes for this commander.
    """
    events, _ = _load_latest_journal_events()
    if not events:
        return MyCarriersResponse(own_carriers=[], squadron_carriers=[])

    # Index CarrierLocation by carrier id so we can attach last-known system,
    # and also track the latest Docked event per carrier so we can reuse its
    # StationServices list when available.
    latest_location_by_id: dict[int, CarrierLocationEvent] = {}
    latest_docked_by_market_id: dict[int, DockedEvent] = {}
    for event in events:
        if isinstance(event, CarrierLocationEvent):
            latest_location_by_id[event.carrier_id] = event
        elif isinstance(event, DockedEvent) and event.station_type == "FleetCarrier":
            latest_docked_by_market_id[event.market_id] = event

    own_carriers: List[CarrierIdentity] = []
    squadron_carriers: List[CarrierIdentity] = []

    # Use CarrierStats as the authoritative source for the commander's carriers.
    seen_ids: set[int] = set()
    for event in events:
        if not isinstance(event, CarrierStatsEvent):
            continue

        carrier_id = event.carrier_id
        if carrier_id in seen_ids:
            continue
        seen_ids.add(carrier_id)

        # Find a matching location if available.
        location = latest_location_by_id.get(carrier_id)

        # Prefer a real Docked event (with StationServices) when available so
        # that the services list matches what we show for the currently docked
        # carrier. Fall back to a minimal synthetic DockedEvent otherwise.
        docked = latest_docked_by_market_id.get(carrier_id)

        if docked is not None:
            identity = _build_identity_from_journal(docked, event, location)
        else:
            fake_docked = DockedEvent(
                timestamp=event.timestamp,
                event=event.event,
                station_name=event.name or "Unknown Carrier",
                station_type="FleetCarrier",
                star_system=location.star_system if location is not None else "",
                system_address=location.system_address if location is not None else 0,
                market_id=carrier_id,
                station_faction={},
                station_government="",
                station_economy="",
                station_economies=[],
                raw_data=event.raw_data,
            )

            identity = _build_identity_from_journal(fake_docked, event, location)

        # By default treat CarrierStats as "own". Current journal data does not
        # reliably expose an "official" squadron carrier, so we do not populate
        # squadron_carriers based solely on DockingAccess.
        own_carriers.append(identity)

    return MyCarriersResponse(
        own_carriers=own_carriers,
        squadron_carriers=squadron_carriers,
    )