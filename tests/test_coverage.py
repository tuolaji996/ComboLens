"""Tests for stock coverage strategies."""

from __future__ import annotations

from datetime import date

import pytest

from packages.portfolio_models.models import (
    OptionType,
    Position,
    SecurityType,
    StrategyType,
)
from packages.strategy_engine import recognize_strategies


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


@pytest.mark.parametrize("multiplier", [100.0, 10.0])
def test_covered_call_basic(multiplier):
    """Covered call: long stock + short call."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0 * multiplier / 100.0, market_value=15000.0, unrealized_pnl=500.0),
        _make_option("call1", "AAPL", -1.0, OptionType.CALL, 150.0, date(2024, 12, 20),
                     multiplier=multiplier, market_value=-300.0, unrealized_pnl=50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.COVERED_CALL
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0
    assert len(strat.legs) == 2
    assert strat.market_value == pytest.approx(14700.0)
    assert strat.unrealized_pnl == pytest.approx(550.0)


@pytest.mark.parametrize("units", [1, 2])
def test_covered_call_multiple_units(units):
    """Covered call with multiple units."""
    positions = [
        _make_stock("stock1", "TSLA", 100.0 * units, market_value=40000.0 * units, unrealized_pnl=1000.0 * units),
        _make_option("call1", "TSLA", -1.0 * units, OptionType.CALL, 210.0, date(2024, 11, 15),
                     market_value=-600.0 * units, unrealized_pnl=100.0 * units),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.COVERED_CALL
    assert strat.quantity == units
    assert strat.market_value == pytest.approx((40000.0 - 600.0) * units)


def test_protective_put_basic():
    """Protective put: long stock + long put."""
    positions = [
        _make_stock("stock1", "SPY", 100.0, market_value=45000.0, unrealized_pnl=2000.0),
        _make_option("put1", "SPY", 1.0, OptionType.PUT, 440.0, date(2024, 11, 15),
                     market_value=600.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.PROTECTIVE_PUT
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0
    assert len(strat.legs) == 2
    assert strat.market_value == pytest.approx(45600.0)
    assert strat.unrealized_pnl == pytest.approx(1950.0)


def test_collar_basic():
    """Collar: long stock + long put + short call."""
    positions = [
        _make_stock("stock1", "NVDA", 100.0, market_value=24000.0, unrealized_pnl=1000.0),
        _make_option("put1", "NVDA", 1.0, OptionType.PUT, 230.0, date(2024, 12, 20),
                     market_value=400.0, unrealized_pnl=-20.0),
        _make_option("call1", "NVDA", -1.0, OptionType.CALL, 250.0, date(2024, 12, 20),
                     market_value=-500.0, unrealized_pnl=30.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.COLLAR
    assert strat.quantity == 1.0
    assert strat.confidence == 1.0
    assert len(strat.legs) == 3
    assert strat.market_value == pytest.approx(23900.0)
    assert strat.unrealized_pnl == pytest.approx(1010.0)


def test_collar_partial_shares():
    """Collar with partial stock coverage (fractional shares allowed)."""
    positions = [
        _make_stock("stock1", "MSFT", 150.0, market_value=60000.0, unrealized_pnl=1500.0),
        _make_option("put1", "MSFT", 1.0, OptionType.PUT, 390.0, date(2024, 11, 15),
                     market_value=300.0, unrealized_pnl=-10.0),
        _make_option("call1", "MSFT", -1.0, OptionType.CALL, 410.0, date(2024, 11, 15),
                     market_value=-200.0, unrealized_pnl=20.0),
    ]
    result = recognize_strategies(positions)

    # Should form 1 collar (100 shares) + 1 stock (50 shares)
    assert len(result) == 2
    collar = [s for s in result if s.strategy_type == StrategyType.COLLAR][0]
    stock = [s for s in result if s.strategy_type == StrategyType.STOCK][0]

    assert collar.quantity == 1.0
    assert stock.quantity == 50.0

    # Check allocation
    collar_stock_leg = [leg for leg in collar.legs if leg.position_id == "stock1"][0]
    assert collar_stock_leg.allocated_quantity == 100.0

    stock_leg = stock.legs[0]
    assert stock_leg.allocated_quantity == 50.0


def test_collar_mismatched_expiry():
    """Collar requires same expiry for put and call."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0, market_value=15000.0, unrealized_pnl=500.0),
        _make_option("put1", "AAPL", 1.0, OptionType.PUT, 145.0, date(2024, 11, 15),
                     market_value=300.0, unrealized_pnl=-10.0),
        _make_option("call1", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     market_value=-200.0, unrealized_pnl=20.0),
    ]
    result = recognize_strategies(positions)

    # Should NOT form collar due to different expiries
    assert not any(s.strategy_type == StrategyType.COLLAR for s in result)
    # Should have stock + two singles or covered call + protective put
    assert len(result) >= 2


def test_short_stock_no_coverage():
    """Short stock does not participate in coverage strategies."""
    positions = [
        _make_stock("stock1", "TSLA", -100.0, market_value=-20000.0, unrealized_pnl=-500.0),
        _make_option("put1", "TSLA", 1.0, OptionType.PUT, 195.0, date(2024, 11, 15),
                     market_value=400.0, unrealized_pnl=50.0),
    ]
    result = recognize_strategies(positions)

    # Should NOT form protective put with short stock
    assert not any(s.strategy_type == StrategyType.PROTECTIVE_PUT for s in result)
    assert len(result) == 2
    assert {s.strategy_type for s in result} == {StrategyType.STOCK, StrategyType.LONG_PUT}


def test_coverage_ambiguity():
    """Overlapping coverage candidates are blocked and emit UNMATCHED."""
    positions = [
        _make_stock("stock1", "SPY", 100.0, market_value=45000.0, unrealized_pnl=1000.0),
        _make_option("put1", "SPY", 1.0, OptionType.PUT, 440.0, date(2024, 11, 15),
                     market_value=600.0, unrealized_pnl=-50.0),
        _make_option("call1", "SPY", -1.0, OptionType.CALL, 460.0, date(2024, 11, 15),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("call2", "SPY", -1.0, OptionType.CALL, 465.0, date(2024, 11, 15),
                     market_value=-250.0, unrealized_pnl=25.0),
    ]
    result = recognize_strategies(positions)

    # Stock can form collar with (put1, call1) or (put1, call2) - ambiguous
    # All should be UNMATCHED
    assert len(result) == 4
    assert all(s.strategy_type == StrategyType.UNMATCHED for s in result)

    # Check stock has special explanation
    stock_strat = [s for s in result if s.legs[0].position_id == "stock1"][0]
    assert "stock overlap" in stock_strat.explanation.lower()


def test_source_quantity_conservation():
    """Allocated quantities sum to original position quantities."""
    positions = [
        _make_stock("stock1", "AAPL", 150.0, market_value=22500.0, unrealized_pnl=750.0),
        _make_option("call1", "AAPL", -2.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     market_value=-600.0, unrealized_pnl=100.0),
    ]
    result = recognize_strategies(positions)

    # Track allocations per position
    allocations = {"stock1": 0.0, "call1": 0.0}
    for strat in result:
        for leg in strat.legs:
            allocations[leg.position_id] += leg.allocated_quantity

    assert allocations["stock1"] == pytest.approx(150.0)
    assert allocations["call1"] == pytest.approx(-2.0)


def test_source_value_conservation():
    """Total allocated values equal original position values."""
    positions = [
        _make_stock("stock1", "SPY", 100.0, market_value=45000.0, unrealized_pnl=2000.0),
        _make_option("put1", "SPY", 1.0, OptionType.PUT, 440.0, date(2024, 11, 15),
                     market_value=600.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    total_value = sum(s.market_value for s in result if s.market_value is not None)
    total_pnl = sum(s.unrealized_pnl for s in result if s.unrealized_pnl is not None)

    assert total_value == pytest.approx(45600.0)
    assert total_pnl == pytest.approx(1950.0)


def test_per_source_signs():
    """Each source position maintains its original sign in all allocations."""
    positions = [
        _make_stock("stock1", "NVDA", 200.0, market_value=48000.0, unrealized_pnl=2000.0),
        _make_option("call1", "NVDA", -2.0, OptionType.CALL, 250.0, date(2024, 12, 20),
                     market_value=-1000.0, unrealized_pnl=60.0),
    ]
    result = recognize_strategies(positions)

    # Check all allocations maintain source signs
    for strat in result:
        for leg in strat.legs:
            if leg.position_id == "stock1":
                assert leg.allocated_quantity > 0  # Long stock stays positive
            elif leg.position_id == "call1":
                assert leg.allocated_quantity < 0  # Short call stays negative


def test_no_cross_account():
    """Coverage strategies don't cross account boundaries."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0, account_id="U1111111", market_value=15000.0),
        _make_option("call1", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     account_id="U2222222", market_value=-300.0),
    ]
    result = recognize_strategies(positions)

    # Should be 2 singles, not covered call
    assert len(result) == 2
    assert not any(s.strategy_type == StrategyType.COVERED_CALL for s in result)


def test_no_cross_currency():
    """Coverage strategies don't cross currency boundaries."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0, currency="USD", market_value=15000.0),
        _make_option("call1", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     currency="EUR", market_value=-300.0),
    ]
    result = recognize_strategies(positions)

    # Should be 2 singles, not covered call
    assert len(result) == 2
    assert not any(s.strategy_type == StrategyType.COVERED_CALL for s in result)


def test_multiplier_10():
    """Coverage works with non-standard multiplier (e.g., 10 for mini options)."""
    positions = [
        _make_stock("stock1", "SPY", 20.0, market_value=9000.0, unrealized_pnl=400.0),
        _make_option("call1", "SPY", -2.0, OptionType.CALL, 460.0, date(2024, 11, 15),
                     multiplier=10.0, market_value=-120.0, unrealized_pnl=12.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.COVERED_CALL
    assert strat.quantity == 2.0  # 2 units of coverage (20 shares / 10 multiplier)


def test_coverage_precedence_over_spreads():
    """Coverage strategies are identified before option spreads."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0, market_value=15000.0, unrealized_pnl=500.0),
        _make_option("call_short", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 11, 15),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("call_long", "AAPL", 1.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     market_value=500.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    # Should form covered call first, leaving long call as single
    # (not a calendar spread)
    covered_calls = [s for s in result if s.strategy_type == StrategyType.COVERED_CALL]
    assert len(covered_calls) == 1

    long_calls = [s for s in result if s.strategy_type == StrategyType.LONG_CALL]
    assert len(long_calls) == 1

    calendars = [s for s in result if s.strategy_type == StrategyType.CALENDAR_CALL]
    assert len(calendars) == 0


def test_reverse_calendar_remaining_singles():
    """Reverse calendar (long near, short far) leaves singles, doesn't match."""
    positions = [
        _make_option("long_near", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 10, 18),
                     market_value=500.0, unrealized_pnl=50.0),
        _make_option("short_far", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 11, 15),
                     market_value=-700.0, unrealized_pnl=-70.0),
    ]
    result = recognize_strategies(positions)

    # Should be 2 singles (no calendar due to wrong direction)
    assert len(result) == 2
    assert {s.strategy_type for s in result} == {StrategyType.LONG_CALL, StrategyType.SHORT_CALL}


def test_true_long_short_orientation():
    """Strategy orientation is determined by actual position signs, not strike order."""
    positions = [
        _make_option("short1", "MSFT", -2.0, OptionType.PUT, 400.0, date(2024, 12, 20),
                     market_value=-1200.0, unrealized_pnl=100.0),
        _make_option("long1", "MSFT", 2.0, OptionType.PUT, 390.0, date(2024, 12, 20),
                     market_value=1600.0, unrealized_pnl=-80.0),
    ]
    result = recognize_strategies(positions)

    # Vertical put spread with correct orientation
    assert len(result) == 1
    strat = result[0]
    assert strat.strategy_type == StrategyType.VERTICAL_PUT
    assert strat.quantity == 2.0

    # Verify legs maintain original signs
    for leg in strat.legs:
        if leg.position_id == "short1":
            assert leg.allocated_quantity < 0
        elif leg.position_id == "long1":
            assert leg.allocated_quantity > 0


def test_phase_precedence():
    """Calendar phase takes precedence over diagonal and vertical."""
    positions = [
        # These could form calendar OR diagonal, calendar wins
        _make_option("short1", "SPY", -1.0, OptionType.CALL, 450.0, date(2024, 10, 18),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("long1", "SPY", 1.0, OptionType.CALL, 450.0, date(2024, 11, 15),
                     market_value=500.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    assert len(result) == 1
    assert result[0].strategy_type == StrategyType.CALENDAR_CALL


def test_diagonal_both_strike_directions():
    """Diagonal spreads work regardless of which leg has higher strike."""
    # Lower strike short, higher strike long
    positions1 = [
        _make_option("short1", "AAPL", -1.0, OptionType.CALL, 180.0, date(2024, 10, 18),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("long1", "AAPL", 1.0, OptionType.CALL, 185.0, date(2024, 11, 15),
                     market_value=450.0, unrealized_pnl=-50.0),
    ]
    result1 = recognize_strategies(positions1)

    # Higher strike short, lower strike long
    positions2 = [
        _make_option("short2", "AAPL", -1.0, OptionType.CALL, 185.0, date(2024, 10, 18),
                     market_value=-450.0, unrealized_pnl=50.0),
        _make_option("long2", "AAPL", 1.0, OptionType.CALL, 180.0, date(2024, 11, 15),
                     market_value=300.0, unrealized_pnl=-30.0),
    ]
    result2 = recognize_strategies(positions2)

    # Both should form diagonals
    assert len(result1) == 1
    assert result1[0].strategy_type == StrategyType.DIAGONAL

    assert len(result2) == 1
    assert result2[0].strategy_type == StrategyType.DIAGONAL


def test_four_singles_no_spread():
    """Four options with no matching criteria remain as singles."""
    positions = [
        _make_option("opt1", "XYZ", 1.0, OptionType.CALL, 100.0, date(2024, 10, 18),
                     market_value=200.0, unrealized_pnl=20.0),
        _make_option("opt2", "XYZ", 1.0, OptionType.CALL, 105.0, date(2024, 10, 18),
                     market_value=150.0, unrealized_pnl=15.0),
        _make_option("opt3", "XYZ", 1.0, OptionType.PUT, 100.0, date(2024, 11, 15),
                     market_value=180.0, unrealized_pnl=18.0),
        _make_option("opt4", "XYZ", 1.0, OptionType.PUT, 95.0, date(2024, 11, 15),
                     market_value=120.0, unrealized_pnl=12.0),
    ]
    result = recognize_strategies(positions)

    # All should be singles (all long, no opposites)
    assert len(result) == 4
    assert all(s.strategy_type in [StrategyType.LONG_CALL, StrategyType.LONG_PUT] for s in result)


def test_small_stock_never_blocks_calendar():
    """2 shares of stock should not block option calendar spread."""
    positions = [
        _make_stock("stock1", "UNH", 2.0, market_value=1000.0, unrealized_pnl=50.0),
        _make_option("call_short", "UNH", -1.0, OptionType.CALL, 500.0, date(2024, 11, 15),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("call_long", "UNH", 1.0, OptionType.CALL, 500.0, date(2024, 12, 20),
                     market_value=500.0, unrealized_pnl=-50.0),
    ]
    result = recognize_strategies(positions)

    # Calendar should form (stock too small to participate)
    calendars = [s for s in result if s.strategy_type == StrategyType.CALENDAR_CALL]
    assert len(calendars) == 1

    # Stock should be unallocated single
    stocks = [s for s in result if s.strategy_type == StrategyType.STOCK]
    assert len(stocks) == 1


def test_collar_precedence_over_substrategies():
    """Collar takes precedence over covered call and protective put."""
    positions = [
        _make_stock("stock1", "AAPL", 100.0, market_value=15000.0, unrealized_pnl=500.0),
        _make_option("put1", "AAPL", 1.0, OptionType.PUT, 145.0, date(2024, 11, 15),
                     market_value=300.0, unrealized_pnl=-10.0),
        _make_option("call1", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 11, 15),
                     market_value=-200.0, unrealized_pnl=20.0),
    ]
    result = recognize_strategies(positions)

    # Should form collar, not covered call + protective put
    assert len(result) == 1
    assert result[0].strategy_type == StrategyType.COLLAR
    assert result[0].quantity == 1.0


def test_blocked_component_allows_disjoint_unique():
    """Blocked ambiguous component doesn't prevent disjoint unique candidates."""
    positions = [
        # Ambiguous collar group for SPY
        _make_stock("stock1", "SPY", 100.0, market_value=45000.0, unrealized_pnl=1000.0),
        _make_option("put1", "SPY", 1.0, OptionType.PUT, 440.0, date(2024, 11, 15),
                     market_value=600.0, unrealized_pnl=-50.0),
        _make_option("call1", "SPY", -1.0, OptionType.CALL, 460.0, date(2024, 11, 15),
                     market_value=-300.0, unrealized_pnl=30.0),
        _make_option("call2", "SPY", -1.0, OptionType.CALL, 465.0, date(2024, 11, 15),
                     market_value=-250.0, unrealized_pnl=25.0),
        # Disjoint unique covered call for AAPL
        _make_stock("stock2", "AAPL", 100.0, market_value=15000.0, unrealized_pnl=500.0),
        _make_option("call3", "AAPL", -1.0, OptionType.CALL, 155.0, date(2024, 12, 20),
                     market_value=-300.0, unrealized_pnl=30.0),
    ]
    result = recognize_strategies(positions)

    # SPY positions should all be UNMATCHED (4 strategies)
    spy_strats = [s for s in result if s.symbol == "SPY"]
    assert len(spy_strats) == 4
    assert all(s.strategy_type == StrategyType.UNMATCHED for s in spy_strats)

    # AAPL should form covered call (1 strategy)
    aapl_strats = [s for s in result if s.symbol == "AAPL"]
    assert len(aapl_strats) == 1
    assert aapl_strats[0].strategy_type == StrategyType.COVERED_CALL
