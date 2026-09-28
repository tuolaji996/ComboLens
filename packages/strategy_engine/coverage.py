"""Stock coverage strategies: collar, covered call, protective put."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from packages.portfolio_models.models import (
    OptionType,
    Position,
    SecurityType,
    Strategy,
    StrategyType,
)


def _find_collar_candidates(
    stock_positions: list[Position],
    option_positions: list[Position],
    ledger: object,
) -> list[tuple[Position, Position, Position]]:
    """Find collar candidates: long stock + long put + short call."""
    from packages.strategy_engine import _AllocationLedger

    if not isinstance(ledger, _AllocationLedger):
        raise TypeError("ledger must be _AllocationLedger")

    option_groups: dict[tuple[float, date], list[Position]] = defaultdict(list)
    for opt in option_positions:
        if (opt.option_type is not None and opt.strike is not None and
            opt.expiration is not None and abs(ledger.get_residual(opt.id)) > 1e-9):
            option_groups[(opt.multiplier, opt.expiration)].append(opt)

    candidates = []
    for stock in stock_positions:
        stock_residual = ledger.get_residual(stock.id)
        if stock_residual <= 0:
            continue

        for (multiplier, _), opts in option_groups.items():
            if stock_residual < multiplier:
                continue

            calls = [o for o in opts if o.option_type == OptionType.CALL]
            puts = [o for o in opts if o.option_type == OptionType.PUT]

            for put_opt in puts:
                if ledger.get_residual(put_opt.id) <= 0:
                    continue
                for call_opt in calls:
                    if ledger.get_residual(call_opt.id) >= 0:
                        continue
                    assert put_opt.strike is not None
                    assert call_opt.strike is not None
                    if put_opt.strike <= call_opt.strike:
                        candidates.append((stock, put_opt, call_opt))
    return candidates


def _find_covered_call_candidates(
    stock_positions: list[Position],
    option_positions: list[Position],
    ledger: object,
) -> list[tuple[Position, Position]]:
    """Find covered call candidates: long stock + short call."""
    from packages.strategy_engine import _AllocationLedger

    if not isinstance(ledger, _AllocationLedger):
        raise TypeError("ledger must be _AllocationLedger")

    option_groups: dict[tuple[float, date], list[Position]] = defaultdict(list)
    for opt in option_positions:
        if (opt.option_type is not None and opt.strike is not None and
            opt.expiration is not None and abs(ledger.get_residual(opt.id)) > 1e-9):
            option_groups[(opt.multiplier, opt.expiration)].append(opt)

    candidates = []
    for stock in stock_positions:
        stock_residual = ledger.get_residual(stock.id)
        if stock_residual <= 0:
            continue

        for (multiplier, _), opts in option_groups.items():
            if stock_residual < multiplier:
                continue

            calls = [o for o in opts if o.option_type == OptionType.CALL]
            for call_opt in calls:
                if ledger.get_residual(call_opt.id) >= 0:
                    continue
                candidates.append((stock, call_opt))
    return candidates


def _find_protective_put_candidates(
    stock_positions: list[Position],
    option_positions: list[Position],
    ledger: object,
) -> list[tuple[Position, Position]]:
    """Find protective put candidates: long stock + long put."""
    from packages.strategy_engine import _AllocationLedger

    if not isinstance(ledger, _AllocationLedger):
        raise TypeError("ledger must be _AllocationLedger")

    option_groups: dict[tuple[float, date], list[Position]] = defaultdict(list)
    for opt in option_positions:
        if (opt.option_type is not None and opt.strike is not None and
            opt.expiration is not None and abs(ledger.get_residual(opt.id)) > 1e-9):
            option_groups[(opt.multiplier, opt.expiration)].append(opt)

    candidates = []
    for stock in stock_positions:
        stock_residual = ledger.get_residual(stock.id)
        if stock_residual <= 0:
            continue

        for (multiplier, _), opts in option_groups.items():
            if stock_residual < multiplier:
                continue

            puts = [o for o in opts if o.option_type == OptionType.PUT]
            for put_opt in puts:
                if ledger.get_residual(put_opt.id) <= 0:
                    continue
                candidates.append((stock, put_opt))
    return candidates


def _detect_ambiguity_collar(candidates: list[tuple[Position, Position, Position]]) -> set[str]:
    """Detect ambiguous collar candidates and return blocked IDs."""
    participation_count: dict[str, int] = defaultdict(int)
    for stock, put_opt, call_opt in candidates:
        participation_count[stock.id] += 1
        participation_count[put_opt.id] += 1
        participation_count[call_opt.id] += 1

    ambiguous = {pid for pid, count in participation_count.items() if count > 1}
    if not ambiguous:
        return set()

    graph: dict[str, set[str]] = defaultdict(set)
    for stock, put_opt, call_opt in candidates:
        ids = [stock.id, put_opt.id, call_opt.id]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                graph[ids[i]].add(ids[j])
                graph[ids[j]].add(ids[i])

    blocked_ids: set[str] = set()
    visited = set()
    for start_id in ambiguous:
        if start_id in visited:
            continue
        component = set()
        to_visit = [start_id]
        while to_visit:
            current = to_visit.pop()
            if current in component:
                continue
            component.add(current)
            visited.add(current)
            for neighbor in graph.get(current, []):
                if neighbor not in component:
                    to_visit.append(neighbor)
        blocked_ids.update(component)
    return blocked_ids


def _detect_ambiguity_pair(candidates: list[tuple[Position, Position]]) -> set[str]:
    """Detect ambiguous two-position candidates and return blocked IDs."""
    participation_count: dict[str, int] = defaultdict(int)
    for pos1, pos2 in candidates:
        participation_count[pos1.id] += 1
        participation_count[pos2.id] += 1

    ambiguous = {pid for pid, count in participation_count.items() if count > 1}
    if not ambiguous:
        return set()

    graph: dict[str, set[str]] = defaultdict(set)
    for pos1, pos2 in candidates:
        graph[pos1.id].add(pos2.id)
        graph[pos2.id].add(pos1.id)

    blocked_ids: set[str] = set()
    visited = set()
    for start_id in ambiguous:
        if start_id in visited:
            continue
        component = set()
        to_visit = [start_id]
        while to_visit:
            current = to_visit.pop()
            if current in component:
                continue
            component.add(current)
            visited.add(current)
            for neighbor in graph.get(current, []):
                if neighbor not in component:
                    to_visit.append(neighbor)
        blocked_ids.update(component)
    return blocked_ids


def _emit_unmatched_strategy(
    pos_id: str, ledger: object, symbol: str, is_stock: bool
) -> Strategy:
    """Emit an UNMATCHED strategy for a blocked position."""
    from packages.strategy_engine import (
        _AllocationLedger,
        _compute_aggregate_pnl,
        _compute_aggregate_value,
        _make_legs,
        _make_strategy_id,
    )

    if not isinstance(ledger, _AllocationLedger):
        raise TypeError("ledger must be _AllocationLedger")

    residual = ledger.get_residual(pos_id)
    pos = ledger.get_position(pos_id)
    allocations = [(pos_id, residual)]
    ledger.allocate(pos_id, residual)
    legs = _make_legs(allocations, ledger)

    if is_stock:
        explanation = "Ambiguous coverage candidates with stock overlap"
    else:
        explanation = "Ambiguous coverage candidates"

    return Strategy(
        id=_make_strategy_id(StrategyType.UNMATCHED, [pos_id]),
        account_id=pos.account_id,
        symbol=pos.symbol,
        currency=pos.currency,
        strategy_type=StrategyType.UNMATCHED,
        quantity=abs(residual),
        name=f"{symbol} Unmatched",
        legs=legs,
        market_value=_compute_aggregate_value(legs),
        unrealized_pnl=_compute_aggregate_pnl(legs),
        confidence=0.0,
        explanation=explanation,
    )


def apply_coverage_strategies(
    stock_positions: list[Position],
    option_positions: list[Position],
    ledger: object,
    blocked_global: set[str],
    symbol: str,
) -> tuple[list[Strategy], set[str]]:
    """Apply coverage strategies tier by tier to avoid false ambiguity.

    Args:
        stock_positions: Stock positions in this partition
        option_positions: Option positions in this partition
        ledger: Allocation ledger
        blocked_global: Global blocked set to update
        symbol: Symbol for this partition

    Returns:
        (strategies, coverage_blocked_ids)
    """
    from packages.strategy_engine import (
        _AllocationLedger,
        _compute_aggregate_pnl,
        _compute_aggregate_value,
        _make_legs,
        _make_strategy_id,
    )

    if not isinstance(ledger, _AllocationLedger):
        raise TypeError("ledger must be _AllocationLedger")

    strategies = []
    all_blocked: set[str] = set()

    # TIER 1: Collar candidates
    collar_cands = _find_collar_candidates(stock_positions, option_positions, ledger)
    collar_blocked = _detect_ambiguity_collar(collar_cands)

    if collar_blocked:
        for pos_id in collar_blocked:
            if pos_id in blocked_global:
                continue
            residual = ledger.get_residual(pos_id)
            if abs(residual) < 1e-9:
                continue
            pos = ledger.get_position(pos_id)
            is_stock = pos.security_type == SecurityType.STOCK
            strategies.append(_emit_unmatched_strategy(pos_id, ledger, symbol, is_stock))
        all_blocked.update(collar_blocked)
        blocked_global.update(collar_blocked)
    else:
        # Process unique collar candidates
        for stock, put_opt, call_opt in collar_cands:
            stock_residual = ledger.get_residual(stock.id)
            put_residual = ledger.get_residual(put_opt.id)
            call_residual = ledger.get_residual(call_opt.id)

            if stock_residual <= 0 or put_residual <= 0 or call_residual >= 0:
                continue

            if stock.id in blocked_global or put_opt.id in blocked_global or call_opt.id in blocked_global:
                continue

            multiplier = put_opt.multiplier
            max_units_from_stock = int(stock_residual / multiplier)
            max_units_from_put = int(put_residual)
            max_units_from_call = int(abs(call_residual))
            units = min(max_units_from_stock, max_units_from_put, max_units_from_call)

            if units <= 0:
                continue

            stock_qty = units * multiplier
            put_qty = float(units)
            call_qty = -float(units)

            if not (ledger.can_allocate(stock.id, stock_qty) and
                    ledger.can_allocate(put_opt.id, put_qty) and
                    ledger.can_allocate(call_opt.id, call_qty)):
                continue

            allocations = [(stock.id, stock_qty), (put_opt.id, put_qty), (call_opt.id, call_qty)]
            for pos_id, qty in allocations:
                ledger.allocate(pos_id, qty)

            legs = _make_legs(allocations, ledger)

            assert put_opt.strike is not None
            assert call_opt.strike is not None
            assert put_opt.expiration is not None

            explanation = f"Long stock + Put ${put_opt.strike:.2f} + Call ${call_opt.strike:.2f} expiring {put_opt.expiration}"

            strategies.append(Strategy(
                id=_make_strategy_id(StrategyType.COLLAR, [stock.id, put_opt.id, call_opt.id]),
                account_id=stock.account_id,
                symbol=symbol,
                currency=stock.currency,
                strategy_type=StrategyType.COLLAR,
                quantity=float(units),
                name=f"{symbol} Collar ×{units}",
                legs=legs,
                market_value=_compute_aggregate_value(legs),
                unrealized_pnl=_compute_aggregate_pnl(legs),
                confidence=1.0,
                explanation=explanation,
            ))

    # TIER 2: Covered call candidates (recompute from updated residuals)
    covered_cands = _find_covered_call_candidates(stock_positions, option_positions, ledger)
    covered_blocked = _detect_ambiguity_pair(covered_cands)

    if covered_blocked:
        for pos_id in covered_blocked:
            if pos_id in blocked_global or pos_id in all_blocked:
                continue
            residual = ledger.get_residual(pos_id)
            if abs(residual) < 1e-9:
                continue
            pos = ledger.get_position(pos_id)
            is_stock = pos.security_type == SecurityType.STOCK
            strategies.append(_emit_unmatched_strategy(pos_id, ledger, symbol, is_stock))
        all_blocked.update(covered_blocked)
        blocked_global.update(covered_blocked)
    else:
        for stock, call_opt in covered_cands:
            stock_residual = ledger.get_residual(stock.id)
            call_residual = ledger.get_residual(call_opt.id)

            if stock_residual <= 0 or call_residual >= 0:
                continue

            if stock.id in blocked_global or call_opt.id in blocked_global:
                continue

            multiplier = call_opt.multiplier
            max_units_from_stock = int(stock_residual / multiplier)
            max_units_from_call = int(abs(call_residual))
            units = min(max_units_from_stock, max_units_from_call)

            if units <= 0:
                continue

            stock_qty = units * multiplier
            call_qty = -float(units)

            if not (ledger.can_allocate(stock.id, stock_qty) and
                    ledger.can_allocate(call_opt.id, call_qty)):
                continue

            allocations = [(stock.id, stock_qty), (call_opt.id, call_qty)]
            for pos_id, qty in allocations:
                ledger.allocate(pos_id, qty)

            legs = _make_legs(allocations, ledger)

            assert call_opt.strike is not None
            assert call_opt.expiration is not None

            explanation = f"Long stock + Call ${call_opt.strike:.2f} expiring {call_opt.expiration}"

            strategies.append(Strategy(
                id=_make_strategy_id(StrategyType.COVERED_CALL, [stock.id, call_opt.id]),
                account_id=stock.account_id,
                symbol=symbol,
                currency=stock.currency,
                strategy_type=StrategyType.COVERED_CALL,
                quantity=float(units),
                name=f"{symbol} Covered Call ×{units}",
                legs=legs,
                market_value=_compute_aggregate_value(legs),
                unrealized_pnl=_compute_aggregate_pnl(legs),
                confidence=1.0,
                explanation=explanation,
            ))

    # TIER 3: Protective put candidates (recompute from updated residuals)
    protective_cands = _find_protective_put_candidates(stock_positions, option_positions, ledger)
    protective_blocked = _detect_ambiguity_pair(protective_cands)

    if protective_blocked:
        for pos_id in protective_blocked:
            if pos_id in blocked_global or pos_id in all_blocked:
                continue
            residual = ledger.get_residual(pos_id)
            if abs(residual) < 1e-9:
                continue
            pos = ledger.get_position(pos_id)
            is_stock = pos.security_type == SecurityType.STOCK
            strategies.append(_emit_unmatched_strategy(pos_id, ledger, symbol, is_stock))
        all_blocked.update(protective_blocked)
        blocked_global.update(protective_blocked)
    else:
        for stock, put_opt in protective_cands:
            stock_residual = ledger.get_residual(stock.id)
            put_residual = ledger.get_residual(put_opt.id)

            if stock_residual <= 0 or put_residual <= 0:
                continue

            if stock.id in blocked_global or put_opt.id in blocked_global:
                continue

            multiplier = put_opt.multiplier
            max_units_from_stock = int(stock_residual / multiplier)
            max_units_from_put = int(put_residual)
            units = min(max_units_from_stock, max_units_from_put)

            if units <= 0:
                continue

            stock_qty = units * multiplier
            put_qty = float(units)

            if not (ledger.can_allocate(stock.id, stock_qty) and
                    ledger.can_allocate(put_opt.id, put_qty)):
                continue

            allocations = [(stock.id, stock_qty), (put_opt.id, put_qty)]
            for pos_id, qty in allocations:
                ledger.allocate(pos_id, qty)

            legs = _make_legs(allocations, ledger)

            assert put_opt.strike is not None
            assert put_opt.expiration is not None

            explanation = f"Long stock + Put ${put_opt.strike:.2f} expiring {put_opt.expiration}"

            strategies.append(Strategy(
                id=_make_strategy_id(StrategyType.PROTECTIVE_PUT, [stock.id, put_opt.id]),
                account_id=stock.account_id,
                symbol=symbol,
                currency=stock.currency,
                strategy_type=StrategyType.PROTECTIVE_PUT,
                quantity=float(units),
                name=f"{symbol} Protective Put ×{units}",
                legs=legs,
                market_value=_compute_aggregate_value(legs),
                unrealized_pnl=_compute_aggregate_pnl(legs),
                confidence=1.0,
                explanation=explanation,
            ))

    return strategies, all_blocked
