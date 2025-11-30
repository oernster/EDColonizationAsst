"""Tests for journal parser"""
import pytest
from src.services.journal_parser import JournalParser
from src.models.journal_events import (
    ColonizationConstructionDepotEvent,
    ColonizationContributionEvent
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
    line = '{"timestamp":"2025-11-29T01:00:00Z","event":"ColonizationContribution","MarketID":123456,"Commodity":"Steel","Commodity_Localised":"Steel","Quantity":100,"TotalQuantity":600,"CreditsReceived":123400}'
    
    event = parser.parse_line(line)
    
    assert event is not None
    assert isinstance(event, ColonizationContributionEvent)
    assert event.market_id == 123456
    assert event.commodity == "Steel"
    assert event.quantity == 100
    assert event.total_quantity == 600
    assert event.credits_received == 123400


def test_parse_irrelevant_event(parser):
    """Test that irrelevant events are ignored"""
    line = '{"timestamp":"2025-11-29T01:00:00Z","event":"Scan","BodyName":"Test Body"}'
    
    event = parser.parse_line(line)
    
    assert event is None


def test_parse_invalid_json(parser):
    """Test handling of invalid JSON"""
    line = 'not valid json'
    
    event = parser.parse_line(line)
    
    assert event is None


def test_parse_empty_line(parser):
    """Test handling of empty line"""
    event = parser.parse_line("")
    
    assert event is None