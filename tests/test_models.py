"""Model tests for portfolio models."""

import json
import math
from datetime import date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.portfolio_models import (
    AccountMetrics,
    OptionType,
    Position,
    SecurityType,
    Snapshot,
    Strategy,
    StrategyLeg,
    StrategyType,
)


class TestPosition:
    """Tests for Position model."""

    def test_valid_stock_position(self):
        """Stock position with all required fields."""
        pos = Position(
            id="pos_1",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=100.0,
            multiplier=1.0,
            market_price=150.0,
            market_value=15000.0,
            unrealized_pnl=500.0,
            underlying_price=150.0,
        )
        assert pos.id == "pos_1"
        assert pos.symbol == "AAPL"
        assert pos.quantity == 100.0
        assert pos.multiplier == 1.0

    def test_valid_option_position(self):
        """Option position with complete terms."""
        pos = Position(
            id="pos_2",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.OPTION,
            quantity=5.0,
            option_type=OptionType.CALL,
            strike=155.0,
            expiration=date(2027, 1, 15),
            multiplier=100.0,
            market_price=10.5,
            market_value=5250.0,
            unrealized_pnl=250.0,
            underlying_price=150.0,
        )
        assert pos.option_type == OptionType.CALL
        assert pos.strike == 155.0
        assert pos.multiplier == 100.0

    def test_option_incomplete_terms_preserved(self):
        """Option with incomplete terms is preserved but won't match."""
        pos = Position(
            id="pos_incomplete",
            account_id="ACC1",
            symbol="XYZ",
            currency="USD",
            security_type=SecurityType.OPTION,
            quantity=1.0,
            option_type=None,
            strike=50.0,
            expiration=None,
            multiplier=100.0,
        )
        assert pos.option_type is None
        assert pos.expiration is None
        assert pos.strike == 50.0

    def test_stock_multiplier_must_be_one(self):
        """Stock positions must have multiplier=1."""
        with pytest.raises(ValueError, match="Stock multiplier must be 1"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.STOCK,
                quantity=100.0,
                multiplier=100.0,
            )

    def test_stock_cannot_have_option_fields(self):
        """Stock positions cannot have option-specific fields."""
        with pytest.raises(ValueError, match="cannot have option-specific fields"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.STOCK,
                quantity=100.0,
                multiplier=1.0,
                option_type=OptionType.CALL,
            )

    def test_option_quantity_must_be_whole(self):
        """Option contracts require integral quantities."""
        with pytest.raises(ValueError, match="must be whole number"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.OPTION,
                quantity=2.5,
                option_type=OptionType.CALL,
                strike=150.0,
                expiration=date(2027, 1, 15),
                multiplier=100.0,
            )

    def test_fractional_stock_quantity_allowed(self):
        """Stock positions can have fractional quantities."""
        pos = Position(
            id="pos_frac",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=10.5,
            multiplier=1.0,
        )
        assert pos.quantity == 10.5

    def test_reject_infinite_quantity(self):
        """Non-finite quantities are rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.STOCK,
                quantity=math.inf,
                multiplier=1.0,
            )

    def test_reject_nan_price(self):
        """NaN prices are rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.STOCK,
                quantity=100.0,
                multiplier=1.0,
                market_price=math.nan,
            )

    def test_negative_strike_rejected(self):
        """Negative strike prices are rejected."""
        with pytest.raises(ValueError, match="Strike must be positive"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.OPTION,
                quantity=1.0,
                option_type=OptionType.CALL,
                strike=-100.0,
                expiration=date(2027, 1, 15),
                multiplier=100.0,
            )

    def test_multiplier_must_be_positive(self):
        """Multiplier must be positive."""
        with pytest.raises(ValueError, match="Multiplier must be positive"):
            Position(
                id="pos_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                security_type=SecurityType.STOCK,
                quantity=100.0,
                multiplier=0.0,
            )

    def test_null_valuations_preserved(self):
        """Missing valuations remain None, not zero."""
        pos = Position(
            id="pos_no_val",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=100.0,
            multiplier=1.0,
            market_price=None,
            market_value=None,
            unrealized_pnl=None,
        )
        assert pos.market_price is None
        assert pos.market_value is None
        assert pos.unrealized_pnl is None

    def test_position_immutable(self):
        """Positions are immutable/frozen."""
        pos = Position(
            id="pos_1",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=100.0,
            multiplier=1.0,
        )
        with pytest.raises(ValidationError):
            pos.quantity = 200.0

    def test_signed_quantities(self):
        """Quantities can be signed (negative for short positions)."""
        short_pos = Position(
            id="pos_short",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=-100.0,
            multiplier=1.0,
        )
        assert short_pos.quantity == -100.0


class TestStrategyLeg:
    """Tests for StrategyLeg model."""

    def test_valid_strategy_leg(self):
        """Valid strategy leg with allocations."""
        leg = StrategyLeg(
            position_id="pos_1",
            allocated_quantity=10.0,
            allocated_value=1500.0,
            allocated_pnl=50.0,
        )
        assert leg.position_id == "pos_1"
        assert leg.allocated_quantity == 10.0

    def test_reject_infinite_allocated_quantity(self):
        """Non-finite allocated values are rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            StrategyLeg(
                position_id="pos_1",
                allocated_quantity=math.inf,
            )

    def test_leg_immutable(self):
        """Strategy legs are immutable/frozen."""
        leg = StrategyLeg(position_id="pos_1", allocated_quantity=10.0)
        with pytest.raises(ValidationError):
            leg.allocated_quantity = 20.0


class TestStrategy:
    """Tests for Strategy model."""

    def test_valid_strategy(self):
        """Valid strategy with legs."""
        strategy = Strategy(
            id="strat_1",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            strategy_type=StrategyType.COVERED_CALL,
            quantity=1.0,
            name="AAPL Covered Call",
            legs=[
                StrategyLeg(position_id="pos_stock", allocated_quantity=100.0),
                StrategyLeg(position_id="pos_call", allocated_quantity=-1.0),
            ],
            market_value=15000.0,
            unrealized_pnl=500.0,
            confidence=0.9,
            explanation="Stock position covered by short call",
        )
        assert strategy.strategy_type == StrategyType.COVERED_CALL
        assert len(strategy.legs) == 2
        assert strategy.quantity == 1.0
        assert strategy.confidence == 0.9

    def test_strategy_quantity_must_be_positive(self):
        """Strategy quantity must be positive."""
        with pytest.raises(ValueError, match="must be positive"):
            Strategy(
                id="strat_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                strategy_type=StrategyType.COVERED_CALL,
                quantity=-1.0,
                name="Bad Strategy",
                legs=[],
                confidence=0.9,
                explanation="Test",
            )

    def test_strategy_includes_account_and_currency(self):
        """Strategy includes account_id and currency."""
        strategy = Strategy(
            id="strat_1",
            account_id="ACC123",
            symbol="AAPL",
            currency="USD",
            strategy_type=StrategyType.LONG_CALL,
            quantity=1.0,
            name="AAPL Long Call",
            legs=[],
            confidence=0.95,
            explanation="Single long call",
        )
        assert strategy.account_id == "ACC123"
        assert strategy.currency == "USD"

    def test_strategy_immutable(self):
        """Strategies are immutable/frozen."""
        strategy = Strategy(
            id="strat_1",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            strategy_type=StrategyType.LONG_CALL,
            quantity=1.0,
            name="Test",
            legs=[],
            confidence=1.0,
            explanation="Test",
        )
        with pytest.raises(ValidationError):
            strategy.quantity = 2.0

    def test_confidence_must_be_in_range(self):
        """Confidence must be in range 0..1."""
        with pytest.raises(ValueError, match="must be in range 0..1"):
            Strategy(
                id="strat_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                strategy_type=StrategyType.LONG_CALL,
                quantity=1.0,
                name="Test",
                legs=[],
                confidence=1.5,
                explanation="Test",
            )

    def test_confidence_boundary_values(self):
        """Confidence accepts boundary values 0 and 1."""
        strat_min = Strategy(
            id="strat_min",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            strategy_type=StrategyType.UNMATCHED,
            quantity=1.0,
            name="Test",
            legs=[],
            confidence=0.0,
            explanation="Lowest confidence",
        )
        assert strat_min.confidence == 0.0

        strat_max = Strategy(
            id="strat_max",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            strategy_type=StrategyType.COLLAR,
            quantity=1.0,
            name="Test",
            legs=[],
            confidence=1.0,
            explanation="Highest confidence",
        )
        assert strat_max.confidence == 1.0

    def test_confidence_must_be_finite(self):
        """Confidence must be finite."""
        with pytest.raises(ValueError, match="must be finite"):
            Strategy(
                id="strat_bad",
                account_id="ACC1",
                symbol="AAPL",
                currency="USD",
                strategy_type=StrategyType.LONG_CALL,
                quantity=1.0,
                name="Test",
                legs=[],
                confidence=math.inf,
                explanation="Test",
            )


class TestAccountMetrics:
    """Tests for AccountMetrics model."""

    def test_valid_account_metrics(self):
        """Valid account metrics."""
        account = AccountMetrics(
            currency="USD",
            net_liquidation=100000.0,
            cash=10000.0,
            daily_pnl=500.0,
            unrealized_pnl=2000.0,
            maintenance_margin=5000.0,
            excess_liquidity=85000.0,
            buying_power=170000.0,
        )
        assert account.currency == "USD"
        assert account.net_liquidation == 100000.0

    def test_reject_infinite_values(self):
        """Non-finite account values are rejected."""
        with pytest.raises(ValueError, match="must be finite"):
            AccountMetrics(
                currency="USD",
                net_liquidation=math.inf,
            )

    def test_account_metrics_immutable(self):
        """Account metrics are immutable/frozen."""
        account = AccountMetrics(currency="USD")
        with pytest.raises(ValidationError):
            account.currency = "EUR"


class TestUnderlying:
    """Tests for Underlying model."""

    def test_underlying_includes_account_and_currency(self):
        """Underlying includes account_id and currency."""
        from packages.portfolio_models import Underlying

        underlying = Underlying(
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            positions=[],
            strategies=[],
        )
        assert underlying.account_id == "ACC1"
        assert underlying.currency == "USD"


class TestSnapshot:
    """Tests for Snapshot model."""

    def test_valid_snapshot(self):
        """Valid snapshot with positions."""
        snapshot = Snapshot(
            as_of=datetime(2026, 9, 14, 16, 0, 0),
            account=AccountMetrics(currency="USD", net_liquidation=100000.0),
            positions=[
                Position(
                    id="pos_1",
                    account_id="ACC1",
                    symbol="AAPL",
                    currency="USD",
                    security_type=SecurityType.STOCK,
                    quantity=100.0,
                    multiplier=1.0,
                ),
            ],
        )
        assert len(snapshot.positions) == 1
        assert snapshot.as_of.year == 2026

    def test_reject_duplicate_position_ids(self):
        """Snapshot rejects duplicate position ids."""
        with pytest.raises(ValueError, match="Duplicate position ids"):
            Snapshot(
                as_of=datetime(2026, 9, 14, 16, 0, 0),
                account=AccountMetrics(currency="USD"),
                positions=[
                    Position(
                        id="pos_1",
                        account_id="ACC1",
                        symbol="AAPL",
                        currency="USD",
                        security_type=SecurityType.STOCK,
                        quantity=100.0,
                        multiplier=1.0,
                    ),
                    Position(
                        id="pos_1",
                        account_id="ACC1",
                        symbol="AAPL",
                        currency="USD",
                        security_type=SecurityType.STOCK,
                        quantity=50.0,
                        multiplier=1.0,
                    ),
                ],
            )

    def test_snapshot_immutable(self):
        """Snapshots are immutable/frozen."""
        snapshot = Snapshot(
            as_of=datetime(2026, 9, 14, 16, 0, 0),
            account=AccountMetrics(currency="USD"),
            positions=[],
        )
        with pytest.raises(ValidationError):
            snapshot.positions = []


class TestMockFixture:
    """Tests for mock_portfolio.json fixture."""

    def test_fixture_loads_successfully(self):
        """Mock fixture loads and validates."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        assert snapshot.as_of.year == 2026
        assert snapshot.as_of.month == 9
        assert snapshot.as_of.day == 14
        assert len(snapshot.positions) > 0

    def test_fixture_contains_unh_positions(self):
        """Fixture contains UNH stock and calendar spread components."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        unh_positions = [p for p in snapshot.positions if p.symbol == "UNH"]

        assert len(unh_positions) == 3  # stock + 2 options
        stock = [p for p in unh_positions if p.security_type == SecurityType.STOCK]
        assert len(stock) == 1
        assert stock[0].quantity == 2.0
        assert stock[0].market_price == 376.97
        assert stock[0].market_value == 753.94

        options = [p for p in unh_positions if p.security_type == SecurityType.OPTION]
        assert len(options) == 2

        # Check for calendar spread components (same strike, different expiry)
        oct_call = [p for p in options if p.expiration == date(2026, 10, 16)]
        nov_call = [p for p in options if p.expiration == date(2026, 11, 20)]
        assert len(oct_call) == 1
        assert len(nov_call) == 1
        assert oct_call[0].strike == 400.0
        assert nov_call[0].strike == 400.0
        assert oct_call[0].quantity == -3.0  # short
        assert nov_call[0].quantity == 3.0  # long

        # Verify exact values from requirements
        assert oct_call[0].market_price == 7.70
        assert oct_call[0].market_value == -2310.0
        assert oct_call[0].unrealized_pnl == 25.0

        assert nov_call[0].market_price == 12.58
        assert nov_call[0].market_value == 3774.0
        assert nov_call[0].unrealized_pnl == -59.70

        # Calendar spread totals (without stock): 1464 value, -34.70 pnl
        calendar_value = oct_call[0].market_value + nov_call[0].market_value
        calendar_pnl = oct_call[0].unrealized_pnl + nov_call[0].unrealized_pnl
        assert calendar_value == 1464.0
        assert calendar_pnl == -34.70

    def test_fixture_contains_dram_collar(self):
        """Fixture contains DRAM collar components."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        dram_positions = [p for p in snapshot.positions if p.symbol == "DRAM"]

        assert len(dram_positions) == 3  # stock + put + call
        stock = [p for p in dram_positions if p.security_type == SecurityType.STOCK]
        assert len(stock) == 1
        assert stock[0].quantity == 100.0

        put = [p for p in dram_positions if p.option_type == OptionType.PUT]
        call = [p for p in dram_positions if p.option_type == OptionType.CALL]
        assert len(put) == 1
        assert len(call) == 1

        # Same expiry for collar
        assert put[0].expiration == call[0].expiration
        # Put strike <= Call strike
        assert put[0].strike <= call[0].strike
        # Long put, short call
        assert put[0].quantity == 1.0
        assert call[0].quantity == -1.0

    def test_fixture_contains_long_calls(self):
        """Fixture contains SPMO and NVDA long calls."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)

        spmo = [p for p in snapshot.positions if p.symbol == "SPMO"]
        assert len(spmo) == 1
        assert spmo[0].security_type == SecurityType.OPTION
        assert spmo[0].option_type == OptionType.CALL
        assert spmo[0].quantity == 1.0
        assert spmo[0].expiration == date(2027, 4, 16)

        nvda = [p for p in snapshot.positions if p.symbol == "NVDA"]
        assert len(nvda) == 1
        assert nvda[0].security_type == SecurityType.OPTION
        assert nvda[0].option_type == OptionType.CALL
        assert nvda[0].quantity == 1.0
        assert nvda[0].expiration == date(2027, 1, 15)

    def test_fixture_contains_qqq_ambiguous_calendars(self):
        """Fixture contains QQQ positions with ambiguous calendar candidates."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        qqq_positions = [p for p in snapshot.positions if p.symbol == "QQQ"]

        # Should have exactly 3 QQQ option positions for ambiguous calendars
        assert len(qqq_positions) == 3

        # Verify the three legs that create competing calendar partners
        dec18_380c = [p for p in qqq_positions if p.expiration == date(2026, 12, 18) and p.strike == 380.0]
        jan15_380c = [p for p in qqq_positions if p.expiration == date(2027, 1, 15) and p.strike == 380.0]
        feb19_380c = [p for p in qqq_positions if p.expiration == date(2027, 2, 19) and p.strike == 380.0]

        assert len(dec18_380c) == 1
        assert dec18_380c[0].quantity == -2.0  # Short 2 contracts
        assert len(jan15_380c) == 1
        assert jan15_380c[0].quantity == 2.0  # Long 2 contracts
        assert len(feb19_380c) == 1
        assert feb19_380c[0].quantity == 1.0  # Long 1 contract

        # These create ambiguous pairings:
        # Option 1: Match all -2 Dec with +2 Jan (leaves +1 Feb unmatched)
        # Option 2: Match -1 Dec with +1 Feb (leaves -1 Dec and +2 Jan as another calendar)

    def test_fixture_contains_xyz_incomplete(self):
        """Fixture contains XYZ position with incomplete option terms."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        xyz = [p for p in snapshot.positions if p.symbol == "XYZ"]

        assert len(xyz) == 1
        assert xyz[0].security_type == SecurityType.OPTION
        # Incomplete: missing option_type or expiration
        assert xyz[0].option_type is None or xyz[0].expiration is None
        # But can have known valuation
        assert xyz[0].market_price == 1.0
        assert xyz[0].market_value == 100.0
        assert xyz[0].unrealized_pnl == -5.0

    def test_fixture_account_totals_consistent(self):
        """Fixture account totals are set."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        account = snapshot.account

        assert account.currency == "USD"
        assert account.net_liquidation is not None
        assert account.cash is not None
        assert account.daily_pnl is not None
        assert account.unrealized_pnl is not None

    def test_fixture_no_duplicate_ids(self):
        """Fixture has no duplicate position ids."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        ids = [p.id for p in snapshot.positions]
        assert len(ids) == len(set(ids))

    def test_fixture_all_finite_values(self):
        """Fixture contains only finite numeric values."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)
        for pos in snapshot.positions:
            assert math.isfinite(pos.quantity)
            assert math.isfinite(pos.multiplier)
            if pos.market_price is not None:
                assert math.isfinite(pos.market_price)
            if pos.market_value is not None:
                assert math.isfinite(pos.market_value)


class TestSerialization:
    """Tests for model serialization."""

    def test_position_serialization_roundtrip(self):
        """Position can be serialized and deserialized."""
        pos = Position(
            id="pos_1",
            account_id="ACC1",
            symbol="AAPL",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=100.0,
            multiplier=1.0,
        )

        json_data = pos.model_dump(mode="json")
        pos_restored = Position(**json_data)

        assert pos_restored.id == pos.id
        assert pos_restored.symbol == pos.symbol
        assert pos_restored.quantity == pos.quantity

    def test_snapshot_serialization_roundtrip(self):
        """Snapshot can be serialized and deserialized."""
        snapshot = Snapshot(
            as_of=datetime(2026, 9, 14, 16, 0, 0),
            account=AccountMetrics(currency="USD", net_liquidation=100000.0),
            positions=[
                Position(
                    id="pos_1",
                    account_id="ACC1",
                    symbol="AAPL",
                    currency="USD",
                    security_type=SecurityType.STOCK,
                    quantity=100.0,
                    multiplier=1.0,
                ),
            ],
        )

        json_str = snapshot.model_dump_json()
        snapshot_restored = Snapshot.model_validate_json(json_str)

        assert snapshot_restored.as_of == snapshot.as_of
        assert len(snapshot_restored.positions) == len(snapshot.positions)


class TestFixtureReconciliation:
    """Tests for fixture numerical reconciliation."""

    def test_fixture_account_reconciliation(self):
        """Fixture account totals reconcile with position values."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)

        # Sum all position market values
        total_market_value = sum(
            p.market_value for p in snapshot.positions if p.market_value is not None
        )

        # Sum all position unrealized P&L
        total_unrealized_pnl = sum(
            p.unrealized_pnl for p in snapshot.positions if p.unrealized_pnl is not None
        )

        # Verify net_liquidation = cash + sum(market_value)
        expected_net_liquidation = snapshot.account.cash + total_market_value
        assert math.isclose(
            snapshot.account.net_liquidation,
            expected_net_liquidation,
            abs_tol=0.01,
        ), f"Expected NL {expected_net_liquidation}, got {snapshot.account.net_liquidation}"

        # Verify unrealized_pnl = sum(position pnl)
        assert math.isclose(
            snapshot.account.unrealized_pnl,
            total_unrealized_pnl,
            abs_tol=0.01,
        ), f"Expected P&L {total_unrealized_pnl}, got {snapshot.account.unrealized_pnl}"

        # Verify excess_liquidity = net_liquidation - maintenance_margin
        expected_excess_liquidity = (
            snapshot.account.net_liquidation - snapshot.account.maintenance_margin
        )
        assert math.isclose(
            snapshot.account.excess_liquidity,
            expected_excess_liquidity,
            abs_tol=0.01,
        ), f"Expected excess {expected_excess_liquidity}, got {snapshot.account.excess_liquidity}"

        # Verify buying_power = 2 * excess_liquidity (illustrative)
        expected_buying_power = 2 * snapshot.account.excess_liquidity
        assert math.isclose(
            snapshot.account.buying_power,
            expected_buying_power,
            abs_tol=0.01,
        ), f"Expected BP {expected_buying_power}, got {snapshot.account.buying_power}"

    def test_fixture_position_values_consistent(self):
        """Position values are consistent with prices and quantities."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            data = json.load(f)

        snapshot = Snapshot(**data)

        for pos in snapshot.positions:
            if pos.market_price is not None and pos.market_value is not None:
                # For stocks: value = price * quantity
                # For options: value = price * quantity * multiplier
                if pos.security_type == SecurityType.STOCK:
                    expected_value = pos.market_price * pos.quantity
                else:
                    expected_value = pos.market_price * pos.quantity * pos.multiplier

                assert math.isclose(
                    pos.market_value, expected_value, abs_tol=0.01
                ), f"{pos.id}: Expected value {expected_value}, got {pos.market_value}"

    def test_fixture_null_valuation_preserved(self):
        """Positions without valuations remain null, tested independently."""
        # Create a test position with null valuations
        pos_null = Position(
            id="pos_test_null",
            account_id="DU1234567",
            symbol="TEST",
            currency="USD",
            security_type=SecurityType.STOCK,
            quantity=10.0,
            multiplier=1.0,
            market_price=None,
            market_value=None,
            unrealized_pnl=None,
        )

        assert pos_null.market_price is None
        assert pos_null.market_value is None
        assert pos_null.unrealized_pnl is None
