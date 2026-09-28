"""Tests for strategy recognition engine."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from packages.portfolio_models.models import (
    OptionType,
    Position,
    SecurityType,
    StrategyType,
)
from packages.strategy_engine import recognize_strategies


def _make_option(
    id: str,
    symbol: str,
    quantity: float,
    option_type: OptionType,
    strike: float,
    expiration: date,
    account_id: str = "U1234567",
    currency: str = "USD",
    multiplier: float = 100.0,
    market_price: float | None = None,
    market_value: float | None = None,
    unrealized_pnl: float | None = None,
) -> Position:
    """Helper to create option position."""
    return Position(
        id=id,
        account_id=account_id,
        symbol=symbol,
        currency=currency,
        security_type=SecurityType.OPTION,
        quantity=quantity,
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        multiplier=multiplier,
        market_price=market_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        underlying_price=None,
    )


def _make_stock(
    id: str,
    symbol: str,
    quantity: float,
    account_id: str = "U1234567",
    currency: str = "USD",
    market_price: float | None = None,
    market_value: float | None = None,
    unrealized_pnl: float | None = None,
) -> Position:
    """Helper to create stock position."""
    return Position(
        id=id,
        account_id=account_id,
        symbol=symbol,
        currency=currency,
        security_type=SecurityType.STOCK,
        quantity=quantity,
        multiplier=1.0,
        market_price=market_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        underlying_price=None,
    )


def test_empty_positions():
    """Empty position list returns empty strategies."""
    result = recognize_strategies([])
    assert result == []


def test_duplicate_ids_raises():
    """Duplicate position IDs raise ValueError."""
    positions = [
        _make_stock("pos1", "AAPL", 100.0),
        _make_stock("pos1", "AAPL", 50.0),
    ]
    with pytest.raises(ValueError, match="Duplicate position IDs"):
        recognize_strategies(positions)


def test_single_stock():
    """Single stock position becomes STOCK strategy."""
    positions = [_make_stock("pos1", "AAPL", 150.5, market_value=22500.0, unrealized_pnl=1200.0)]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.STOCK
    assert strat.symbol == "AAPL"
    assert strat.quantity == 150.5
    assert strat.confidence == 1.0
    assert len(strat.legs) == 1
    assert strat.legs[0].position_id == "pos1"
    assert strat.legs[0].allocated_quantity == 150.5
    assert strat.market_value == 22500.0
    assert strat.unrealized_pnl == 1200.0


def test_long_call():
    """Long call position becomes LONG_CALL strategy."""
    positions = [
        _make_option(
            "call1", "AAPL", 2.0, OptionType.CALL, 150.0,
            date(2024, 12, 20), market_value=1000.0, unrealized_pnl=200.0
        )
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.LONG_CALL
    assert strat.quantity == 2.0
    assert strat.confidence == 1.0
    assert strat.market_value == 1000.0
    assert strat.unrealized_pnl == 200.0


def test_short_put():
    """Short put position becomes SHORT_PUT strategy."""
    positions = [
        _make_option(
            "put1", "TSLA", -3.0, OptionType.PUT, 200.0,
            date(2024, 11, 15), market_value=-4500.0, unrealized_pnl=300.0
        )
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.SHORT_PUT
    assert strat.quantity == 3.0
    assert strat.confidence == 1.0


def test_calendar_call_basic():
    """Calendar call: short near + long far, same strike."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18), market_value=-500.0, unrealized_pnl=-50.0),
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15), market_value=700.0, unrealized_pnl=100.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.CALENDAR_CALL
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0
    assert len(strat.legs) == 2
    assert strat.market_value == pytest.approx(200.0)
    assert strat.unrealized_pnl == pytest.approx(50.0)


def test_calendar_call_quantity_3():
    """Calendar call with quantity 3."""
    positions = [
        _make_option("short", "UNH", -3.0, OptionType.CALL, 590.0, date(2024, 10, 18), market_value=-3735.0, unrealized_pnl=-435.0),
        _make_option("long", "UNH", 3.0, OptionType.CALL, 590.0, date(2024, 11, 15), market_value=5460.0, unrealized_pnl=660.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.CALENDAR_CALL
    assert strat.quantity == 3.0
    assert strat.market_value == pytest.approx(1725.0)
    assert strat.unrealized_pnl == pytest.approx(225.0)


def test_calendar_put():
    """Calendar put: short near + long far, same strike."""
    positions = [
        _make_option("short", "NVDA", -2.0, OptionType.PUT, 120.0, date(2024, 10, 18), market_value=-800.0, unrealized_pnl=100.0),
        _make_option("long", "NVDA", 2.0, OptionType.PUT, 120.0, date(2024, 12, 20), market_value=1200.0, unrealized_pnl=-100.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.CALENDAR_PUT
    assert strat.quantity == 2.0
    assert strat.confidence == 1.0


def test_calendar_mismatched_quantity():
    """Calendar with mismatched quantities allocates minimum, retains residual."""
    positions = [
        _make_option("short", "SPY", -5.0, OptionType.CALL, 450.0, date(2024, 10, 18), market_value=-2500.0, unrealized_pnl=-250.0),
        _make_option("long", "SPY", 2.0, OptionType.CALL, 450.0, date(2024, 11, 15), market_value=1400.0, unrealized_pnl=200.0),
    ]
    result = recognize_strategies(positions)

    # Should have: 1 calendar (qty 2) + 1 short call (qty 3)
    assert len(result) == 2

    calendar = [s for s in result if s.strategy_type == StrategyType.CALENDAR_CALL][0]
    assert calendar.quantity == 2.0

    short = [s for s in result if s.strategy_type == StrategyType.SHORT_CALL][0]
    assert short.quantity == 3.0

    # Check value conservation
    total_value = sum(s.market_value for s in result if s.market_value is not None)
    assert total_value == pytest.approx(-1100.0, abs=1.0)


def test_diagonal():
    """Diagonal spread: same right, different strikes and expiries."""
    positions = [
        _make_option("short", "AAPL", -1.0, OptionType.CALL, 180.0, date(2024, 10, 18), market_value=-300.0, unrealized_pnl=50.0),
        _make_option("long", "AAPL", 1.0, OptionType.CALL, 185.0, date(2024, 11, 15), market_value=450.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.DIAGONAL
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0
    assert strat.market_value == pytest.approx(150.0)


def test_vertical_call():
    """Vertical call spread: same expiry, different strikes, opposite signs."""
    positions = [
        _make_option("long", "MSFT", 2.0, OptionType.CALL, 400.0, date(2024, 12, 20), market_value=2000.0, unrealized_pnl=200.0),
        _make_option("short", "MSFT", -2.0, OptionType.CALL, 410.0, date(2024, 12, 20), market_value=-1200.0, unrealized_pnl=100.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.VERTICAL_CALL
    assert strat.quantity == 2.0
    assert strat.confidence == 1.0
    assert strat.market_value == pytest.approx(800.0)
    assert strat.unrealized_pnl == pytest.approx(300.0)


def test_vertical_put():
    """Vertical put spread: same expiry, different strikes, opposite signs."""
    positions = [
        _make_option("long", "SPY", 1.0, OptionType.PUT, 440.0, date(2024, 11, 15), market_value=600.0, unrealized_pnl=-50.0),
        _make_option("short", "SPY", -1.0, OptionType.PUT, 435.0, date(2024, 11, 15), market_value=-400.0, unrealized_pnl=50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.VERTICAL_PUT
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0


def test_incomplete_option_terms():
    """Options with incomplete terms are marked UNMATCHED."""
    positions = [
        Position(
            id="incomplete",
            account_id="U1234567",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.OPTION,
            quantity=1.0,
            option_type=None,  # Missing
            strike=None,
            expiration=None,
            multiplier=100.0,
        )
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.UNMATCHED
    assert strat.confidence == 0.0
    assert "Incomplete option terms" in strat.explanation


def test_null_values_propagate():
    """Null market values propagate to aggregate as null."""
    positions = [
        _make_option("call1", "AAPL", 1.0, OptionType.CALL, 150.0, date(2024, 12, 20)),  # No values
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.market_value is None
    assert strat.unrealized_pnl is None


def test_partial_null_in_strategy():
    """If any leg has null value, aggregate is null."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18)),  # No value
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15), market_value=700.0),
    ]
    result = recognize_strategies(positions)

    calendar = [s for s in result if s.strategy_type == StrategyType.CALENDAR_CALL][0]
    assert calendar.market_value is None


def test_different_multipliers():
    """Different multipliers cannot form a multi-leg strategy."""
    positions = [
        _make_option("opt1", "XYZ", 1.0, OptionType.CALL, 100.0, date(2024, 12, 20), multiplier=100.0),
        _make_option("opt2", "XYZ", -1.0, OptionType.CALL, 100.0, date(2024, 12, 20), multiplier=10.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 2
    assert {s.strategy_type for s in result} == {StrategyType.LONG_CALL, StrategyType.SHORT_CALL}


def test_account_segregation():
    """Positions in different accounts don't match."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18), account_id="U1111111"),
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15), account_id="U2222222"),
    ]
    result = recognize_strategies(positions)

    # Should be 2 singles, not a calendar
    assert len(result) == 2
    assert all(s.strategy_type in [StrategyType.SHORT_CALL, StrategyType.LONG_CALL] for s in result)


def test_currency_segregation():
    """Positions in different currencies don't match."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18), currency="USD"),
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15), currency="EUR"),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 2
    assert all(s.strategy_type in [StrategyType.SHORT_CALL, StrategyType.LONG_CALL] for s in result)


def test_symbol_segregation():
    """Positions in different symbols don't match."""
    positions = [
        _make_stock("pos1", "AAPL", 100.0),
        _make_stock("pos2", "MSFT", 50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 2
    assert {s.symbol for s in result} == {"AAPL", "MSFT"}


def test_deterministic_ordering():
    """Results are independent of input ordering."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18)),
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15)),
        _make_stock("stock", "AAPL", 100.0),
    ]

    result1 = recognize_strategies(positions)
    result2 = recognize_strategies(list(reversed(positions)))
    result3 = recognize_strategies([positions[2], positions[0], positions[1]])

    # Compare IDs and types (deterministic)
    def extract_key(strategies):
        return [(s.id, s.strategy_type.value, s.quantity) for s in strategies]

    assert extract_key(result1) == extract_key(result2)
    assert extract_key(result1) == extract_key(result3)


def test_ambiguity_qqq_fixture():
    """QQQ ambiguity: 2 long Oct + 2 short Nov, each has 2 partners = ambiguous."""
    positions = [
        _make_option("long1", "QQQ", 1.0, OptionType.CALL, 480.0, date(2024, 10, 18)),
        _make_option("long2", "QQQ", 1.0, OptionType.CALL, 480.0, date(2024, 10, 18)),
        _make_option("short1", "QQQ", -1.0, OptionType.CALL, 480.0, date(2024, 11, 15)),
        _make_option("short2", "QQQ", -1.0, OptionType.CALL, 480.0, date(2024, 11, 15)),
    ]
    result = recognize_strategies(positions)

    # All 4 should be singles (SHORT_CALL or LONG_CALL), no calendars
    assert len(result) == 4
    assert all(s.strategy_type in [StrategyType.SHORT_CALL, StrategyType.LONG_CALL] for s in result)


def test_source_quantity_conservation():
    """Allocated quantities sum to original position quantities."""
    positions = [
        _make_option("short", "SPY", -5.0, OptionType.CALL, 450.0, date(2024, 10, 18), market_value=-2500.0),
        _make_option("long", "SPY", 2.0, OptionType.CALL, 450.0, date(2024, 11, 15), market_value=1400.0),
    ]
    result = recognize_strategies(positions)

    # Track allocations per position
    allocations = {"short": 0.0, "long": 0.0}
    for strat in result:
        for leg in strat.legs:
            allocations[leg.position_id] += leg.allocated_quantity

    assert allocations["short"] == pytest.approx(-5.0)
    assert allocations["long"] == pytest.approx(2.0)


def test_value_conservation():
    """Total allocated value equals original position values."""
    positions = [
        _make_option("short", "SPY", -3.0, OptionType.CALL, 450.0, date(2024, 10, 18), market_value=-1500.0, unrealized_pnl=-150.0),
        _make_option("long", "SPY", 3.0, OptionType.CALL, 450.0, date(2024, 11, 15), market_value=2100.0, unrealized_pnl=210.0),
    ]
    result = recognize_strategies(positions)

    total_value = sum(s.market_value for s in result if s.market_value is not None)
    total_pnl = sum(s.unrealized_pnl for s in result if s.unrealized_pnl is not None)

    assert total_value == pytest.approx(600.0)
    assert total_pnl == pytest.approx(60.0)


def test_raw_immutability():
    """Original positions remain unmodified."""
    positions = [
        _make_option("short", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18)),
        _make_option("long", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15)),
    ]

    original_quantities = [p.quantity for p in positions]
    recognize_strategies(positions)

    # Positions should be unchanged
    assert [p.quantity for p in positions] == original_quantities


def test_fixture_mock_snapshot():
    """Test against mock_portfolio.json fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
    with open(fixture_path) as f:
        data = json.load(f)

    positions = [Position(**p) for p in data["positions"]]
    result = recognize_strategies(positions)

    # Check UNH calendar call (×3)
    unh_calendars = [s for s in result if s.symbol == "UNH" and s.strategy_type == StrategyType.CALENDAR_CALL]
    assert len(unh_calendars) == 1
    assert unh_calendars[0].quantity == 3.0

    # Check UNH stock (2 shares)
    unh_stock = [s for s in result if s.symbol == "UNH" and s.strategy_type == StrategyType.STOCK]
    assert len(unh_stock) == 1
    assert unh_stock[0].quantity == 2.0

    # Check single long calls (SPMO, NVDA)
    spmo = [s for s in result if s.symbol == "SPMO"]
    assert len(spmo) == 1
    assert spmo[0].strategy_type == StrategyType.LONG_CALL

    nvda = [s for s in result if s.symbol == "NVDA"]
    assert len(nvda) == 1
    assert nvda[0].strategy_type == StrategyType.LONG_CALL

    # DRAM collar: 100 shares + 1 put + 1 short call, same expiry
    dram = [s for s in result if s.symbol == "DRAM"]
    assert len(dram) == 1
    assert dram[0].strategy_type == StrategyType.COLLAR

    # Total strategies should cover all positions
    assert len(result) > 0


def test_fixture_ambiguity_examples():
    """Competing QQQ calendar partners stay explicitly unmatched."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
    with open(fixture_path) as f:
        data = json.load(f)

    positions = [Position(**p) for p in data["positions"] if p["symbol"] == "QQQ"]
    result = recognize_strategies(positions)

    # All three QQQ legs remain unmatched due to competing partners
    assert len(result) == 3
    assert all(s.symbol == "QQQ" for s in result)
    assert all(s.strategy_type == StrategyType.UNMATCHED for s in result)
