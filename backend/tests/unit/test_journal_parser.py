"""Tests for journal parser"""

import json
from pathlib import Path

import pytest

from src.services.journal_parser import JournalParser
from src.models.journal_events import (
    ColonizationConstructionDepotEvent,
    ColonizationContributionEvent,
    LocationEvent,
    FSDJumpEvent,
    DockedEvent,
    CommanderEvent,
    CarrierLocationEvent,
    CarrierStatsEvent,
    CarrierTradeOrderEvent,
)


def test_parse_construction_depot_event(parser, sample_journal_line):
    """Test parsing ColonizationConstructionDepot event"""
    event = parser.parse_line(sample_journal_line)

    assert event is not None
    assert isinstance(event, ColonizationConstructionDepotEvent)
    assert event.market_id == 123456
    assert event.station_name == "Test Station"
    assert event.system_name == "Test System"
    assert event.construction_progress == 50.0
    assert len(event.commodities) == 1


def test_parse_contribution_event(parser):
    """Test parsing ColonizationContribution event"""
    line = (
        '{"timestamp":"2025-11-29T01:00:00Z","event":"ColonizationContribution",'
        '"MarketID":123456,"Commodity":"Steel","Commodity_Localised":"Steel",'
        '"Quantity":100,"TotalQuantity":600,"CreditsReceived":123400}'
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, ColonizationContributionEvent)
    assert event.market_id == 123456
    assert event.commodity == "Steel"
    assert event.quantity == 100
    assert event.total_quantity == 600
    assert event.credits_received == 123400


def test_parse_contribution_event_contributions_array(parser):
    """Test parsing ColonisationContribution with Contributions array schema."""
    line = json.dumps(
        {
            "timestamp": "2025-12-15T20:37:20Z",
            "event": "ColonisationContribution",
            "MarketID": 3960951554,
            "Contributions": [
                {
                    "Name": "$Titanium_name;",
                    "Name_Localised": "Titanium",
                    "Amount": 23,
                }
            ],
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, ColonizationContributionEvent)
    assert event.market_id == 3960951554
    assert event.commodity == "$Titanium_name;"
    assert event.commodity_localised == "Titanium"
    assert event.quantity == 23
    assert event.total_quantity == 23


def test_parse_location_event(parser):
    """Test parsing Location event"""
    line = json.dumps(
        {
            "timestamp": "2025-11-29T01:00:00Z",
            "event": "Location",
            "StarSystem": "Test System",
            "SystemAddress": 987654,
            "StarPos": [1.0, 2.0, 3.0],
            "StationName": "Test Station",
            "StationType": "Coriolis",
            "MarketID": 123456,
            "Docked": True,
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, LocationEvent)
    assert event.star_system == "Test System"
    assert event.system_address == 987654
    assert event.docked is True
    assert event.station_name == "Test Station"
    assert event.station_type == "Coriolis"
    assert event.market_id == 123456


def test_parse_fsd_jump_event(parser):
    """Test parsing FSDJump event"""
    line = json.dumps(
        {
            "timestamp": "2025-11-29T01:05:00Z",
            "event": "FSDJump",
            "StarSystem": "Next System",
            "SystemAddress": 111222,
            "StarPos": [10.0, 20.0, 30.0],
            "JumpDist": 12.5,
            "FuelUsed": 3.2,
            "FuelLevel": 10.0,
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, FSDJumpEvent)
    assert event.star_system == "Next System"
    assert event.jump_dist == 12.5
    assert event.fuel_used == 3.2
    assert event.fuel_level == 10.0


def test_parse_docked_event(parser):
    """Test parsing Docked event"""
    line = json.dumps(
        {
            "timestamp": "2025-11-29T01:10:00Z",
            "event": "Docked",
            "StationName": "Dock Station",
            "StationType": "Outpost",
            "StarSystem": "Dock System",
            "SystemAddress": 333444,
            "MarketID": 777,
            "StationFaction": {"Name": "Faction"},
            "StationGovernment": "Democracy",
            "StationEconomy": "Industrial",
            "StationEconomies": [],
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, DockedEvent)
    assert event.station_name == "Dock Station"
    assert event.station_type == "Outpost"
    assert event.star_system == "Dock System"
    assert event.system_address == 333444
    assert event.market_id == 777
    assert event.station_government == "Democracy"


def test_parse_commander_event(parser):
    """Test parsing Commander event"""
    line = json.dumps(
        {
            "timestamp": "2025-11-29T01:15:00Z",
            "event": "Commander",
            "Name": "CMDR Test",
            "FID": "ABC123",
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, CommanderEvent)
    assert event.name == "CMDR Test"
    assert event.fid == "ABC123"


def test_parse_irrelevant_event(parser):
    """Test that irrelevant events are ignored"""
    line = '{"timestamp":"2025-11-29T01:00:00Z","event":"Scan","BodyName":"Test Body"}'

    event = parser.parse_line(line)

    assert event is None


def test_parse_invalid_json(parser):
    """Test handling of invalid JSON"""
    line = "not valid json"

    event = parser.parse_line(line)

    assert event is None


def test_parse_empty_line(parser):
    """Test handling of empty line"""
    event = parser.parse_line("")

    assert event is None


@pytest.mark.asyncio
async def test_parse_file_multiple_events(tmp_path: Path):
    """Test parse_file reads all relevant events from a file."""
    parser = JournalParser()
    file_path = tmp_path / "Journal.2025-11-29T010000.01.log"

    lines = [
        # Relevant: ColonizationConstructionDepot
        '{"timestamp":"2025-11-29T01:00:00Z","event":"ColonizationConstructionDepot",'
        '"MarketID":123456,"StationName":"Test Station","StationType":"Depot",'
        '"StarSystem":"Test System","SystemAddress":987654,"ConstructionProgress":25.0,'
        '"Commodities":[{"Name":"Steel","Name_Localised":"Steel","Total":1000,"Delivered":250,"Payment":1000}]}',
        # Irrelevant: Scan
        '{"timestamp":"2025-11-29T01:01:00Z","event":"Scan","BodyName":"Something"}',
        # Relevant: ColonizationContribution
        '{"timestamp":"2025-11-29T01:02:00Z","event":"ColonizationContribution","MarketID":123456,'
        '"Commodity":"Steel","Quantity":100,"TotalQuantity":350,"CreditsReceived":100000}',
    ]

    file_path.write_text("\n".join(lines), encoding="utf-8")

    events = parser.parse_file(file_path)

    # Should get exactly the two relevant colonization events
    assert len(events) == 2
    assert isinstance(events[0], ColonizationConstructionDepotEvent)
    assert isinstance(events[1], ColonizationContributionEvent)


def test_parse_construction_depot_with_resources_required(parser):
    """ColonizationConstructionDepot using ResourcesRequired should be normalised correctly."""
    data = {
        "timestamp": "2025-11-29T01:00:00Z",
        "event": "ColonizationConstructionDepot",
        "MarketID": 54321,
        "StationName": "Resources Station",
        "StationType": "Depot",
        "StarSystem": "Resources System",
        "SystemAddress": 222333,
        "ConstructionProgress": 75.0,
        "ResourcesRequired": [
            {
                "Name": "Steel",
                "Name_Localised": "Steel Local",
                "RequiredAmount": 1000,
                "ProvidedAmount": 400,
                "Payment": 1234,
            }
        ],
    }
    line = json.dumps(data)

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, ColonizationConstructionDepotEvent)
    assert event.market_id == 54321
    assert event.system_name == "Resources System"
    assert len(event.commodities) == 1
    comm = event.commodities[0]
    assert comm["Name"] == "Steel"
    assert comm["Name_Localised"] == "Steel Local"
    # ResourcesRequired should have been mapped to Total/Delivered
    assert comm["Total"] == 1000
    assert comm["Delivered"] == 400


def test_parse_line_generic_error_returns_none(parser):
    """Non-JSON errors (e.g. bad timestamp) should be caught and return None."""
    # Valid JSON, but invalid timestamp format that will cause fromisoformat to raise
    line = json.dumps({"timestamp": "not-a-timestamp", "event": "Location"})
    event = parser.parse_line(line)
    assert event is None


def test_parse_file_missing_file_returns_empty_list(tmp_path: Path):
    """parse_file should handle missing files and return an empty list."""
    parser = JournalParser()
    missing_path = tmp_path / "Journal.missing.log"

    events = parser.parse_file(missing_path)

    assert events == []


def test_parse_file_skips_lines_that_raise(parser, tmp_path: Path):
    """Exceptions from parse_line should be logged and skipped, not raised."""
    parser = parser  # explicit for clarity
    file_path = tmp_path / "Journal.bad_line.log"
    file_path.write_text(
        '{"timestamp":"2025-11-29T01:00:00Z","event":"Location","StarSystem":"Sys","SystemAddress":1}\n',
        encoding="utf-8",
    )

    def bad_parse_line(line: str):
        raise RuntimeError("boom")

    # Monkeypatch the instance method for this parser only
    parser.parse_line = bad_parse_line  # type: ignore[assignment]

    events = parser.parse_file(file_path)

    # The bad line should have been skipped and no events returned
    assert events == []


# ---------------------------------------------------------------------------
# New tests: carrier-related journal events
# ---------------------------------------------------------------------------


def test_parse_carrier_location_event(parser):
    """Test parsing CarrierLocation event."""
    line = json.dumps(
        {
            "timestamp": "2025-12-15T10:50:30Z",
            "event": "CarrierLocation",
            "CarrierType": "FleetCarrier",
            "CarrierID": 3700569600,
            "StarSystem": "Lupus Dark Region BQ-Y d66",
            "SystemAddress": 2278253693331,
            "BodyID": 0,
        }
    )

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, CarrierLocationEvent)
    assert event.carrier_id == 3700569600
    assert event.star_system == "Lupus Dark Region BQ-Y d66"
    assert event.system_address == 2278253693331


def test_parse_carrier_stats_event(parser):
    """Test parsing CarrierStats event including name, callsign and raw payload."""
    data = {
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
    }
    line = json.dumps(data)

    event = parser.parse_line(line)

    assert event is not None
    assert isinstance(event, CarrierStatsEvent)
    assert event.carrier_id == 3700569600
    assert event.name == "MIDNIGHT ELOQUENCE"
    assert event.callsign == "X7J-BQG"
    # Raw data should retain SpaceUsage for later aggregation
    assert "SpaceUsage" in event.raw_data
    assert event.raw_data["SpaceUsage"]["Cargo"] == 2316


def test_parse_carrier_trade_order_sale_and_buy(parser):
    """Test parsing CarrierTradeOrder for both sell and buy orders."""
    # Sell order example
    sale_line = json.dumps(
        {
            "timestamp": "2025-12-15T11:17:37Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "titanium",
            "SaleOrder": 23,
            "Price": 4446,
        }
    )

    sale_event = parser.parse_line(sale_line)
    assert sale_event is not None
    assert isinstance(sale_event, CarrierTradeOrderEvent)
    assert sale_event.carrier_id == 3700569600
    assert sale_event.commodity == "titanium"
    assert sale_event.sale_order == 23
    assert sale_event.purchase_order == 0
    assert sale_event.price == 4446

    # Buy order example
    buy_line = json.dumps(
        {
            "timestamp": "2025-12-15T11:20:15Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "tritium",
            "PurchaseOrder": 5,
            "Price": 51294,
        }
    )

    buy_event = parser.parse_line(buy_line)
    assert buy_event is not None
    assert isinstance(buy_event, CarrierTradeOrderEvent)
    assert buy_event.carrier_id == 3700569600
    assert buy_event.commodity == "tritium"
    assert buy_event.purchase_order == 5
    assert buy_event.sale_order == 0
    assert buy_event.price == 51294


def test_parse_carrier_trade_order_cancel(parser):
    """CarrierTradeOrder with only CancelTrade still yields an event but no orders."""
    cancel_line = json.dumps(
        {
            "timestamp": "2025-12-15T11:20:20Z",
            "event": "CarrierTradeOrder",
            "CarrierID": 3700569600,
            "CarrierType": "FleetCarrier",
            "BlackMarket": False,
            "Commodity": "tritium",
            "CancelTrade": True,
        }
    )

    event = parser.parse_line(cancel_line)

    assert event is not None
    assert isinstance(event, CarrierTradeOrderEvent)
    assert event.carrier_id == 3700569600
    assert event.commodity == "tritium"
    # No explicit SaleOrder or PurchaseOrder were provided
    assert event.sale_order == 0
    assert event.purchase_order == 0
