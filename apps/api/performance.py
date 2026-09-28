"""Strategy performance enrichment.

Enriches strategies with lifecycle performance summaries from history records.
Matches by exact allocated leg signature, account_id, and currency.
"""

from datetime import UTC

from packages.portfolio_models.models import (
    Snapshot,
    Strategy,
    StrategyHistory,
    StrategyPerformance,
    StrategyType,
)


def _legs_match(strategy: Strategy, history: StrategyHistory) -> bool:
    """Check if strategy legs exactly match history leg signature."""
    if len(strategy.legs) != len(history.legs):
        return False

    # Sort both by position_id, then allocated_quantity for deterministic comparison
    strat_legs = sorted(
        [(leg.position_id, leg.allocated_quantity) for leg in strategy.legs],
        key=lambda x: (x[0], x[1])
    )
    hist_legs = sorted(
        [(leg.position_id, leg.allocated_quantity) for leg in history.legs],
        key=lambda x: (x[0], x[1])
    )

    return strat_legs == hist_legs


def _find_matching_history(strategy: Strategy, snapshot: Snapshot) -> StrategyHistory | None:
    """Find matching history record for strategy."""
    matches = []

    for history in snapshot.strategy_history:
        # Match account_id and currency
        if history.account_id != strategy.account_id:
            continue
        if history.currency != strategy.currency:
            continue

        # If history has strategy_id, it MUST match strategy.id
        if history.strategy_id is not None and history.strategy_id != strategy.id:
            continue

        # Match exact allocated leg signature
        if not _legs_match(strategy, history):
            continue

        matches.append(history)

    # Reject ambiguous duplicates
    if len(matches) == 0:
        return None
    if len(matches) > 1:
        return None  # Ambiguous, multiple matches

    return matches[0]


def enrich_strategies_with_performance(
    strategies: list[Strategy], snapshot: Snapshot
) -> list[Strategy]:
    """Enrich strategies with performance summaries from snapshot history.

    Returns new Strategy instances with performance field populated.
    Unmatched strategies or those with incomplete/invalid history get 'unavailable'.
    UNMATCHED strategies are always marked unavailable regardless of history.
    """
    enriched = []

    for strategy in strategies:
        # Early check: UNMATCHED strategies are always unavailable
        if strategy.strategy_type == StrategyType.UNMATCHED:
            performance = StrategyPerformance(
                source="unavailable",
                opened_at=None,
                realized_pnl=None,
                fees=None,
                total_pnl=None,
                reason="Strategy type is unmatched"
            )
            enriched.append(strategy.model_copy(update={'performance': performance}))
            continue

        # Find matching history
        history = _find_matching_history(strategy, snapshot)

        # Determine performance
        if history is None:
            # No matching history
            performance = StrategyPerformance(
                source="unavailable",
                opened_at=None,
                realized_pnl=None,
                fees=None,
                total_pnl=None,
                reason="No matching history found"
            )
        elif not history.complete:
            # Incomplete history
            performance = StrategyPerformance(
                source="unavailable",
                opened_at=None,
                realized_pnl=None,
                fees=None,
                total_pnl=None,
                reason="History is incomplete"
            )
        elif not history.pnl_excludes_fees:
            # Fee basis incorrect
            performance = StrategyPerformance(
                source="unavailable",
                opened_at=None,
                realized_pnl=None,
                fees=None,
                total_pnl=None,
                reason="Fee basis is invalid"
            )
        elif strategy.unrealized_pnl is None:
            # Missing unrealized P&L
            performance = StrategyPerformance(
                source="unavailable",
                opened_at=None,
                realized_pnl=None,
                fees=None,
                total_pnl=None,
                reason="Missing unrealized P&L"
            )
        else:
            # Safe datetime comparison: treat naive as_of as UTC
            snapshot_dt = snapshot.as_of if snapshot.as_of.tzinfo is not None else snapshot.as_of.replace(tzinfo=UTC)

            if history.opened_at > snapshot_dt:
                # Future opening date
                performance = StrategyPerformance(
                    source="unavailable",
                    opened_at=None,
                    realized_pnl=None,
                    fees=None,
                    total_pnl=None,
                    reason="Opening date is in the future"
                )
            else:
                # Valid history: total = unrealized + realized - fees
                total_pnl = strategy.unrealized_pnl + history.realized_pnl - history.fees
                performance = StrategyPerformance(
                    source="mock_history",
                    opened_at=history.opened_at,
                    realized_pnl=history.realized_pnl,
                    fees=history.fees,
                    total_pnl=total_pnl,
                    reason=None
                )

        # Create enriched strategy with performance using model_copy
        enriched.append(strategy.model_copy(update={'performance': performance}))

    return enriched
