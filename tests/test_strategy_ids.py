"""Test strategy ID collision resistance and determinism."""

from datetime import date

from packages.portfolio_models.models import (
    OptionType,
    Position,
    SecurityType,
    StrategyType,
)
from packages.strategy_engine import _make_strategy_id, recognize_strategies


def test_strategy_id_collision_resistance():
    """Test that underscore-containing leg IDs don't collide."""
    # Scenario A: leg_ids = ['a_b', 'c']
    id_a = _make_strategy_id(StrategyType.CALENDAR_CALL, ['a_b', 'c'])

    # Scenario B: leg_ids = ['a', 'b_c']
    id_b = _make_strategy_id(StrategyType.CALENDAR_CALL, ['a', 'b_c'])

    # These must be different despite joining to same underscore-delimited string
    assert id_a != id_b, f"Collision detected: {id_a} == {id_b}"


def test_strategy_id_permutation_stable():
    """Test that leg order doesn't affect ID."""
    id_forward = _make_strategy_id(StrategyType.CALENDAR_CALL, ['x', 'y', 'z'])
    id_reverse = _make_strategy_id(StrategyType.CALENDAR_CALL, ['z', 'y', 'x'])
    id_shuffled = _make_strategy_id(StrategyType.CALENDAR_CALL, ['y', 'z', 'x'])

    assert id_forward == id_reverse == id_shuffled


def test_integration_collision_scenario():
    """Test full engine with collision-prone leg IDs produces unique strategies."""
    base_date = date(2024, 1, 15)
    far_date = date(2024, 2, 15)
    strike = 100.0

    # Option A: near short id='a_b', far long id='c'
    positions_a = [
        Position(
            id='a_b',
            account_id='U123',
            symbol='SPY',
            currency='USD',
            security_type=SecurityType.OPTION,
            quantity=-1.0,
            option_type=OptionType.CALL,
            strike=strike,
            expiration=base_date,
            multiplier=100.0,
        ),
        Position(
            id='c',
            account_id='U123',
            symbol='SPY',
            currency='USD',
            security_type=SecurityType.OPTION,
            quantity=1.0,
            option_type=OptionType.CALL,
            strike=strike,
            expiration=far_date,
            multiplier=100.0,
        ),
    ]

    # Option B: near short id='a', far long id='b_c'
    positions_b = [
        Position(
            id='a',
            account_id='U123',
            symbol='SPY',
            currency='USD',
            security_type=SecurityType.OPTION,
            quantity=-1.0,
            option_type=OptionType.CALL,
            strike=strike,
            expiration=base_date,
            multiplier=100.0,
        ),
        Position(
            id='b_c',
            account_id='U123',
            symbol='SPY',
            currency='USD',
            security_type=SecurityType.OPTION,
            quantity=1.0,
            option_type=OptionType.CALL,
            strike=strike,
            expiration=far_date,
            multiplier=100.0,
        ),
    ]

    strategies_a = recognize_strategies(positions_a)
    strategies_b = recognize_strategies(positions_b)

    # Both should produce exactly one CALENDAR_CALL strategy
    calendar_a = [s for s in strategies_a if s.strategy_type == StrategyType.CALENDAR_CALL]
    calendar_b = [s for s in strategies_b if s.strategy_type == StrategyType.CALENDAR_CALL]

    assert len(calendar_a) == 1, f"Expected 1 CALENDAR_CALL in A, got {len(calendar_a)}"
    assert len(calendar_b) == 1, f"Expected 1 CALENDAR_CALL in B, got {len(calendar_b)}"

    # The two strategies must have different IDs
    assert calendar_a[0].id != calendar_b[0].id, \
        f"Collision in full engine: {calendar_a[0].id} == {calendar_b[0].id}"
