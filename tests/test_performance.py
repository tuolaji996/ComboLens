"""Performance enrichment tests."""

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.performance import enrich_strategies_with_performance
from packages.portfolio_models.models import (
    Snapshot,
    StrategyHistory,
    StrategyHistoryLeg,
    StrategyPerformance,
)
from packages.strategy_engine import recognize_strategies


def test_unmatched_rejects_even_exact_history(base_snapshot: Snapshot) -> None:
    strategies = recognize_strategies(base_snapshot.positions)
    unmatched = next(s for s in strategies if s.strategy_type.value == "UNMATCHED")
    history = base_snapshot.strategy_history[0].model_copy(update={
        "account_id": unmatched.account_id,
        "currency": unmatched.currency,
        "legs": [StrategyHistoryLeg(position_id=leg.position_id, allocated_quantity=leg.allocated_quantity)
                 for leg in unmatched.legs],
    })
    snapshot = base_snapshot.model_copy(update={"strategy_history": [history]})
    result = enrich_strategies_with_performance([unmatched], snapshot)[0]
    assert result.performance.source == "unavailable"
    assert result.performance.total_pnl is None


def test_api_performance_consistency_and_raw_preservation(base_snapshot: Snapshot) -> None:
    from fastapi.testclient import TestClient

    from apps.api.main import create_app
    from apps.api.providers import MockPortfolioProvider

    with TestClient(create_app(MockPortfolioProvider())) as client:
        flat = client.get("/api/v1/strategies").json()
        nested = client.get("/api/v1/underlyings").json()
        by_id = {s["id"]: s for u in nested for s in u["strategies"]}
        assert by_id == {s["id"]: s for s in flat}
        nvda = next(s for s in flat if s["symbol"] == "NVDA")
        assert nvda["performance"]["total_pnl"] == pytest.approx(363.05)
        assert client.get("/api/v1/positions").json() == [
            p.model_dump(mode="json") for p in base_snapshot.positions
        ]


@pytest.fixture
def base_snapshot() -> Snapshot:
    """Load mock portfolio fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "mock_portfolio.json"
    return Snapshot.model_validate_json(fixture_path.read_text())


def test_fixture_performance_totals(base_snapshot: Snapshot) -> None:
    """Verify expected performance totals from fixture."""
    strategies = recognize_strategies(base_snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, base_snapshot)

    # UNH calendar spread
    unh_cal = next(s for s in enriched if s.symbol == "UNH" and "Calendar" in s.name)
    assert unh_cal.performance.source == "mock_history"
    assert unh_cal.performance.total_pnl == pytest.approx(-38.60, abs=0.01)

    # DRAM collar
    dram = next(s for s in enriched if s.symbol == "DRAM")
    assert dram.performance.source == "mock_history"
    assert dram.performance.total_pnl == pytest.approx(173.70, abs=0.01)

    # SPMO long call
    spmo = next(s for s in enriched if s.symbol == "SPMO")
    assert spmo.performance.source == "mock_history"
    assert spmo.performance.total_pnl == pytest.approx(124.35, abs=0.01)

    # NVDA long call
    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "mock_history"
    assert nvda.performance.realized_pnl == 45.0
    assert nvda.performance.fees == 1.95
    assert nvda.performance.total_pnl == pytest.approx(363.05, abs=0.01)

    # UNH stock
    unh_stock = next(s for s in enriched if s.symbol == "UNH" and s.strategy_type.name == "STOCK")
    assert unh_stock.performance.source == "mock_history"
    assert unh_stock.performance.total_pnl == pytest.approx(15.0, abs=0.01)


def test_missing_history_unavailable(base_snapshot: Snapshot) -> None:
    """Strategy without matching history returns unavailable performance."""
    snapshot = base_snapshot.model_copy(update={"strategy_history": []})
    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    for s in enriched:
        assert s.performance.source == "unavailable"
        assert s.performance.total_pnl is None
        assert s.performance.realized_pnl is None
        assert s.performance.fees is None
        assert s.performance.reason is not None


@pytest.mark.parametrize("field,value,expected_reason", [
    ("complete", False, "incomplete"),
    ("pnl_excludes_fees", False, "Fee basis"),
])
def test_invalid_history_flags(base_snapshot: Snapshot, field: str, value: bool, expected_reason: str) -> None:
    """Invalid history flags produce unavailable performance."""
    history = base_snapshot.strategy_history[3]  # NVDA
    modified = history.model_copy(update={field: value})
    snapshot = base_snapshot.model_copy(update={"strategy_history": [modified]})

    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "unavailable"
    assert nvda.performance.total_pnl is None
    assert expected_reason in nvda.performance.reason


def test_missing_unrealized_pnl_unavailable(base_snapshot: Snapshot) -> None:
    """Strategy with missing unrealized_pnl returns unavailable."""
    strategies = recognize_strategies(base_snapshot.positions)
    # Force unrealized_pnl to None for one strategy
    modified = strategies[0].model_copy(update={"unrealized_pnl": None})
    strategies_with_none = [modified] + strategies[1:]

    enriched = enrich_strategies_with_performance(strategies_with_none, base_snapshot)
    assert enriched[0].performance.source == "unavailable"
    assert "Missing unrealized" in enriched[0].performance.reason


@pytest.mark.parametrize("field,value", [("account_id", "WRONG"), ("currency", "EUR"), ("strategy_id", "WRONG")])
def test_account_currency_mismatch_no_match(base_snapshot: Snapshot, field: str, value: str) -> None:
    """Mismatched account_id or currency produces no match."""
    history = base_snapshot.strategy_history[3]  # NVDA
    wrong_account = history.model_copy(update={field: value})
    snapshot = base_snapshot.model_copy(update={"strategy_history": [wrong_account]})

    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "unavailable"
    assert "No matching" in nvda.performance.reason


def test_wrong_leg_quantity_no_match(base_snapshot: Snapshot) -> None:
    """Wrong allocated_quantity produces no match."""
    history = base_snapshot.strategy_history[3]  # NVDA single leg
    wrong_qty = StrategyHistoryLeg(position_id=history.legs[0].position_id, allocated_quantity=2.0)
    modified = history.model_copy(update={"legs": [wrong_qty]})
    snapshot = base_snapshot.model_copy(update={"strategy_history": [modified]})

    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "unavailable"


def test_duplicate_matching_records_unavailable(base_snapshot: Snapshot) -> None:
    """Duplicate matching history records produce unavailable (ambiguous)."""
    history = base_snapshot.strategy_history[3]  # NVDA
    snapshot = base_snapshot.model_copy(update={"strategy_history": [history, history]})

    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "unavailable"


def test_future_opened_unavailable(base_snapshot: Snapshot) -> None:
    """Future opened_at produces unavailable performance."""
    future_time = base_snapshot.as_of.replace(year=2027)
    history = base_snapshot.strategy_history[3].model_copy(update={"opened_at": future_time})
    snapshot = base_snapshot.model_copy(update={"strategy_history": [history]})

    strategies = recognize_strategies(snapshot.positions)
    enriched = enrich_strategies_with_performance(strategies, snapshot)

    nvda = next(s for s in enriched if s.symbol == "NVDA")
    assert nvda.performance.source == "unavailable"
    assert "future" in nvda.performance.reason


def test_history_validation_timezone_aware() -> None:
    """StrategyHistory requires timezone-aware opened_at."""
    with pytest.raises(ValidationError, match="timezone-aware"):
        StrategyHistory(
            account_id="ACC1",
            currency="USD",
            legs=[StrategyHistoryLeg(position_id="pos1", allocated_quantity=1.0)],
            opened_at=datetime(2026, 9, 1, 10, 0, 0),  # Naive
            realized_pnl=0.0,
            fees=0.0,
            complete=True,
            pnl_excludes_fees=True,
        )


def test_history_validation_negative_fees() -> None:
    """StrategyHistory rejects negative fees."""
    with pytest.raises(ValidationError, match="non-negative"):
        StrategyHistory(
            account_id="ACC1",
            currency="USD",
            legs=[StrategyHistoryLeg(position_id="pos1", allocated_quantity=1.0)],
            opened_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
            realized_pnl=0.0,
            fees=-1.0,
            complete=True,
            pnl_excludes_fees=True,
        )


@pytest.mark.parametrize("value", [math.inf, math.nan])
def test_history_validation_finite_values(value: float) -> None:
    """StrategyHistory rejects non-finite fees and pnl."""
    with pytest.raises(ValidationError, match="finite"):
        StrategyHistory(
            account_id="ACC1",
            currency="USD",
            legs=[StrategyHistoryLeg(position_id="pos1", allocated_quantity=1.0)],
            opened_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
            realized_pnl=value,
            fees=0.0,
            complete=True,
            pnl_excludes_fees=True,
        )


def test_history_validation_unique_leg_ids() -> None:
    """StrategyHistory rejects duplicate position_ids in legs."""
    with pytest.raises(ValidationError, match="Duplicate position_ids"):
        StrategyHistory(
            account_id="ACC1",
            currency="USD",
            legs=[
                StrategyHistoryLeg(position_id="pos1", allocated_quantity=1.0),
                StrategyHistoryLeg(position_id="pos1", allocated_quantity=-1.0),
            ],
            opened_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
            realized_pnl=0.0,
            fees=0.0,
            complete=True,
            pnl_excludes_fees=True,
        )


def test_performance_validation_non_negative_fees() -> None:
    """StrategyPerformance rejects negative fees."""
    with pytest.raises(ValidationError, match="non-negative"):
        StrategyPerformance(
            source="mock_history",
            opened_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
            realized_pnl=0.0,
            fees=-5.0,
            total_pnl=0.0,
        )


def test_performance_validation_finite_values() -> None:
    """StrategyPerformance rejects non-finite values."""
    with pytest.raises(ValidationError, match="finite"):
        StrategyPerformance(
            source="mock_history",
            opened_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
            realized_pnl=math.inf,
            fees=0.0,
            total_pnl=0.0,
        )
