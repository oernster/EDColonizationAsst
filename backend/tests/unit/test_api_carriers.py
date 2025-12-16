"""Tests for Fleet carrier REST API routes using real components (no mocking framework).

These tests exercise the new /api/carriers endpoints against realistic in-memory
journal data written to a temporary directory. They use the real JournalParser
and FastAPI router wiring; only simple monkeypatching of helper functions is used
to point the API at the test journal directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import httpx
import pytest
from fastapi import FastAPI

import src.api.carriers as carriers_api
from src.api.carriers import router as carriers_router


def _write_journal_file(journal_dir: Path, events: list[dict]) -> Path:
    """Helper to write a Journal.*.log file with the given JSON events."""
    journal_dir.mkdir(parents=True, exist_ok=True)
    file_path = journal_dir / "Journal.2025-12-15T104644.01.log"
    lines = [json.dumps(e) for e in events]
    file_path.write_text("\n".join(lines), encoding="utf-8")
    return file_path


@pytest.mark.asyncio
async def test_carriers_current_and_state_with_fleet_carrier(
    tmp_path: Path, monkeypatch: Callable
):
    """End-to-end test for /api/carriers/current and /api/carriers/current/state.

    Verifies that:
      - The API recognises a FleetCarrier docking context.
      - Carrier identity is built from CarrierStats/Docked/CarrierLocation.
      - Cargo, buy_orders, sell_orders and total_cargo_tonnage are populated
        from CarrierTradeOrder and CarrierStats events.
    """
    journal_dir = tmp_path / "journals"

    events = [
        {
            "timestamp": "2025-12-15T10:50:30Z",
            "event": "CarrierLocation",
            "CarrierType": "FleetCarrier",
            "CarrierID": 3700569600,
            "StarSystem": "Test System",
            "SystemAddress": 2278253693331,
            "BodyID": 0,
        },
        {
            "timestamp": "2025-12-15T10:55:20Z",
            "event": "CarrierStats",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "Callsign": "X7J-BQG",
            "Name": "MIDNIGHT ELOQUENCE",
            "DockingAccess": "squadron",
            "SpaceUsage": {
                "TotalCapacity": 25000,
                "Crew": 3370,
                "Cargo": 2316,
                "CargoSpaceReserved": 0,
                "ShipPacks": 0,
                "ModulePacks": 0,
                "FreeSpace": 19314,
            },
            "Crew": [
                {
                    "CrewRole": "Captain",
                    "Activated": True,
                    "Enabled": True,
                    "CrewName": "Swara Phillips",
                },
                {
                    "CrewRole": "Exploration",
                    "Activated": True,
                    "Enabled": True,
                    "CrewName": "Roland Lechner",
                },
                {
                    "CrewRole": "Outfitting",
                    "Activated": True,
                    "Enabled": True,
                    "CrewName": "Alvaro Stokes",
                },
            ],
        },
        {
            "timestamp": "2025-12-15T10:54:47Z",
            "event": "Docked",
            "StationName": "X7J-BQG",
            "StationType": "FleetCarrier",
            "StarSystem": "Test System",
            "SystemAddress": 2278253693331,
            "MarketID": 3700569600,
            "StationFaction": {"Name": "FleetCarrier"},
            "StationGovernment": "$government_Carrier;",
            "StationEconomy": "$economy_Carrier;",
            "StationEconomies": [
                {"Name": "$economy_Carrier;", "Proportion": 1.0},
            ],
        },
        {
            "timestamp": "2025-12-15T11:17:37Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "titanium",
            "Commodity_Localised": "Titanium",
            "SaleOrder": 23,
            "Price": 4446,
        },
        {
            "timestamp": "2025-12-15T11:20:15Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "tritium",
            "Commodity_Localised": "Tritium",
            "PurchaseOrder": 5,
            "Price": 51294,
        },
    ]

    journal_file = _write_journal_file(journal_dir, events)

    # Point the carriers API at our test journal directory/file
    monkeypatch.setattr(carriers_api, "get_journal_directory", lambda: journal_dir)
    monkeypatch.setattr(
        carriers_api,
        "get_latest_journal_file",
        lambda _dir: journal_file,
    )

    app = FastAPI()
    app.include_router(carriers_router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # /api/carriers/current
        resp_current = await client.get("/api/carriers/current")
        assert resp_current.status_code == 200
        current_data = resp_current.json()
        assert current_data["docked_at_carrier"] is True
        carrier = current_data["carrier"]
        assert carrier is not None
        assert carrier["name"] == "MIDNIGHT ELOQUENCE"
        assert carrier["callsign"] == "X7J-BQG"
        assert carrier["last_seen_system"] == "Test System"

        # /api/carriers/current/state
        resp_state = await client.get("/api/carriers/current/state")
        assert resp_state.status_code == 200
        state_data = resp_state.json()
        carrier_state = state_data["carrier"]
        assert carrier_state is not None

        identity = carrier_state["identity"]
        assert identity["name"] == "MIDNIGHT ELOQUENCE"
        assert identity["callsign"] == "X7J-BQG"

        # total_cargo_tonnage from CarrierStats.SpaceUsage.Cargo
        assert carrier_state["total_cargo_tonnage"] == 2316
        # total_capacity_tonnage and free_space_tonnage from CarrierStats.SpaceUsage
        assert carrier_state["total_capacity_tonnage"] == 25000
        assert carrier_state["free_space_tonnage"] == 19314

        # Services should include at least exploration and outfitting based on CarrierStats.Crew
        services = identity.get("services") or []
        assert isinstance(services, list)
        assert "exploration" in services
        assert "outfitting" in services

        # Cargo derived from SELL orders (titanium)
        cargo = carrier_state["cargo"]
        assert isinstance(cargo, list)
        assert any(
            item["commodity_name"] == "titanium" and item["stock"] == 23
            for item in cargo
        )

        # Buy and sell orders from CarrierTradeOrder
        buy_orders = carrier_state["buy_orders"]
        sell_orders = carrier_state["sell_orders"]

        assert any(
            order["commodity_name"] == "tritium"
            and order["original_amount"] == 5
            and order["order_type"] == "buy"
            for order in buy_orders
        )
        assert any(
            order["commodity_name"] == "titanium"
            and order["original_amount"] == 23
            and order["order_type"] == "sell"
            for order in sell_orders
        )


@pytest.mark.asyncio
async def test_carriers_current_state_clears_sold_out_cargo(
    tmp_path: Path, monkeypatch: Callable
):
    """
    When a SELL order is later reported with zero Stock/Outstanding, the
    cargo view should no longer show positive stock for that commodity.
    """
    journal_dir = tmp_path / "journals"

    events = [
        {
            "timestamp": "2025-12-15T10:50:30Z",
            "event": "CarrierLocation",
            "CarrierType": "FleetCarrier",
            "CarrierID": 3700569600,
            "StarSystem": "Test System",
            "SystemAddress": 2278253693331,
            "BodyID": 0,
        },
        {
            "timestamp": "2025-12-15T10:55:20Z",
            "event": "CarrierStats",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "Callsign": "X7J-BQG",
            "Name": "MIDNIGHT ELOQUENCE",
            "DockingAccess": "squadron",
        },
        {
            "timestamp": "2025-12-15T10:54:47Z",
            "event": "Docked",
            "StationName": "X7J-BQG",
            "StationType": "FleetCarrier",
            "StarSystem": "Test System",
            "SystemAddress": 2278253693331,
            "MarketID": 3700569600,
            "StationFaction": {"Name": "FleetCarrier"},
            "StationGovernment": "$government_Carrier;",
            "StationEconomy": "$economy_Carrier;",
            "StationEconomies": [
                {"Name": "$economy_Carrier;", "Proportion": 1.0},
            ],
        },
        # Another commodity that remains on the carrier (e.g. fruit and vegetables)
        {
            "timestamp": "2025-12-15T11:16:00Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "fruitandvegetables",
            "Commodity_Localised": "Fruit and Vegetables",
            "SaleOrder": 9,
            "Price": 1000,
        },
        # Initial SELL order for titanium with 23t for sale.
        {
            "timestamp": "2025-12-15T11:17:37Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "titanium",
            "Commodity_Localised": "Titanium",
            "SaleOrder": 23,
            "Price": 4446,
        },
        # Later update after the commander has bought all titanium. The journal
        # reports zero stock/outstanding; our aggregation should no longer show
        # positive stock for titanium in the cargo view.
        {
            "timestamp": "2025-12-15T11:25:00Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "titanium",
            "Commodity_Localised": "Titanium",
            "SaleOrder": 23,
            "Stock": 0,
            "Outstanding": 0,
            "Price": 4446,
        },
    ]

    journal_file = _write_journal_file(journal_dir, events)

    monkeypatch.setattr(carriers_api, "get_journal_directory", lambda: journal_dir)
    monkeypatch.setattr(
        carriers_api,
        "get_latest_journal_file",
        lambda _dir: journal_file,
    )

    app = FastAPI()
    app.include_router(carriers_router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp_state = await client.get("/api/carriers/current/state")
        assert resp_state.status_code == 200
        state_data = resp_state.json()
        carrier_state = state_data["carrier"]
        assert carrier_state is not None

        cargo = carrier_state["cargo"]
        assert isinstance(cargo, list)

        # Fruit and vegetables should still be present with 9t stock.
        assert any(
            item["commodity_name"] == "fruitandvegetables" and item["stock"] == 9
            for item in cargo
        )

        # Titanium should not report any positive stock after the zero-stock
        # CarrierTradeOrder update.
        assert not any(
            item["commodity_name"] == "titanium" and item["stock"] > 0
            for item in cargo
        )


@pytest.mark.asyncio
async def test_carriers_mine_lists_own_and_squadron(
    tmp_path: Path, monkeypatch: Callable
):
    """Test /api/carriers/mine discovers own and squadron carriers from CarrierStats/CarrierLocation."""
    journal_dir = tmp_path / "journals"

    events = [
        {
            "timestamp": "2025-12-15T10:50:30Z",
            "event": "CarrierLocation",
            "CarrierType": "FleetCarrier",
            "CarrierID": 3700569600,
            "StarSystem": "Test System",
            "SystemAddress": 2278253693331,
            "BodyID": 0,
        },
        {
            "timestamp": "2025-12-15T10:55:20Z",
            "event": "CarrierStats",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "Callsign": "X7J-BQG",
            "Name": "MIDNIGHT ELOQUENCE",
            "DockingAccess": "squadron",
        },
    ]

    journal_file = _write_journal_file(journal_dir, events)

    monkeypatch.setattr(carriers_api, "get_journal_directory", lambda: journal_dir)
    monkeypatch.setattr(
        carriers_api,
        "get_latest_journal_file",
        lambda _dir: journal_file,
    )

    app = FastAPI()
    app.include_router(carriers_router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/carriers/mine")
        assert resp.status_code == 200
        data = resp.json()

        own_carriers = data["own_carriers"]
        squadron_carriers = data["squadron_carriers"]

        assert len(own_carriers) == 1
        assert own_carriers[0]["name"] == "MIDNIGHT ELOQUENCE"
        # DockingAccess 'squadron' is now surfaced on the identity, but we no longer
        # infer an official squadron carrier list from it.
        assert own_carriers[0]["docking_access"] == "squadron"
        assert len(squadron_carriers) == 0


@pytest.mark.asyncio
async def test_carriers_current_state_404_when_not_docked_at_carrier(
    tmp_path: Path, monkeypatch: Callable
):
    """When the latest Docked event is not at a FleetCarrier, /current/state should return 404."""
    journal_dir = tmp_path / "journals"

    events = [
        {
            "timestamp": "2025-12-15T10:55:20Z",
            "event": "CarrierStats",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "Callsign": "X7J-BQG",
            "Name": "MIDNIGHT ELOQUENCE",
            "DockingAccess": "squadron",
        },
        {
            "timestamp": "2025-12-15T10:56:00Z",
            "event": "Docked",
            "StationName": "Some Station",
            "StationType": "Coriolis",
            "StarSystem": "Some System",
            "SystemAddress": 123,
            "MarketID": 111,
            "StationFaction": {"Name": "Faction"},
            "StationGovernment": "Democracy",
            "StationEconomy": "Industrial",
            "StationEconomies": [],
        },
    ]

    journal_file = _write_journal_file(journal_dir, events)

    monkeypatch.setattr(carriers_api, "get_journal_directory", lambda: journal_dir)
    monkeypatch.setattr(
        carriers_api,
        "get_latest_journal_file",
        lambda _dir: journal_file,
    )

    app = FastAPI()
    app.include_router(carriers_router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        resp_current = await client.get("/api/carriers/current")
        assert resp_current.status_code == 200
        assert resp_current.json()["docked_at_carrier"] is False

        resp_state = await client.get("/api/carriers/current/state")
        assert resp_state.status_code == 404
        assert "not currently docked" in resp_state.json()["detail"]
