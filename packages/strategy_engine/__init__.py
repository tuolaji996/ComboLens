"""Strategy recognition and allocation engine."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from enum import Enum

from packages.portfolio_models.models import (
    OptionType,
    Position,
    SecurityType,
    Strategy,
    StrategyLeg,
    StrategyType,
)

__all__ = ["recognize_strategies", "_AllocationLedger", "_make_legs", "_compute_aggregate_value", "_compute_aggregate_pnl", "_make_strategy_id"]


class _SpreadPhase(Enum):
    """Strategy matching phases in priority order."""
    CALENDAR = "calendar"
    DIAGONAL = "diagonal"
    VERTICAL = "vertical"


class _AllocationLedger:
    """Tracks residual quantities with overspend/sign guard."""

    def __init__(self, positions: list[Position]) -> None:
        self._positions = {p.id: p for p in positions}
        self._residuals: dict[str, float] = {p.id: p.quantity for p in positions}

    def get_residual(self, position_id: str) -> float:
        return self._residuals.get(position_id, 0.0)

    def can_allocate(self, position_id: str, quantity: float) -> bool:
        """Check if allocation respects residual sign and magnitude."""
        residual = self.get_residual(position_id)
        if abs(residual) < 1e-9:
            return False
        # Same sign and not exceeding magnitude
        return (residual * quantity > 0) and (abs(quantity) <= abs(residual) + 1e-9)

    def allocate(self, position_id: str, quantity: float) -> None:
        """Allocate signed quantity from residual."""
        if not self.can_allocate(position_id, quantity):
            raise ValueError(f"Invalid allocation: {position_id} residual={self.get_residual(position_id)}, qty={quantity}")
        self._residuals[position_id] -= quantity

    def get_position(self, position_id: str) -> Position:
        return self._positions[position_id]

    def get_nonzero_residuals(self) -> dict[str, float]:
        return {pid: qty for pid, qty in self._residuals.items() if abs(qty) > 1e-9}


def _deterministic_sort_key(p: Position) -> tuple[str, str, str, str, str, float, date, float, str]:
    return (
        p.account_id, p.symbol, p.currency, p.security_type.value,
        p.option_type.value if p.option_type else "",
        p.strike or 0.0, p.expiration or date.min, p.multiplier, p.id,
    )


def _make_strategy_id(strategy_type: StrategyType, leg_ids: list[str]) -> str:
    canonical = json.dumps(sorted(leg_ids), separators=(',', ':'), sort_keys=True)
    hash_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return f"strat_{strategy_type.value.lower()}_{hash_digest}"


def _make_legs(allocations: list[tuple[str, float]], ledger: _AllocationLedger) -> list[StrategyLeg]:
    legs = []
    for position_id, allocated_qty in allocations:
        pos = ledger.get_position(position_id)
        allocated_value = None
        allocated_pnl = None
        if abs(pos.quantity) > 1e-9:
            proportion = allocated_qty / pos.quantity
            if pos.market_value is not None:
                allocated_value = pos.market_value * proportion
            if pos.unrealized_pnl is not None:
                allocated_pnl = pos.unrealized_pnl * proportion
        legs.append(StrategyLeg(
            position_id=position_id,
            allocated_quantity=allocated_qty,
            allocated_value=allocated_value,
            allocated_pnl=allocated_pnl,
        ))
    return legs


def _compute_aggregate_value(legs: list[StrategyLeg]) -> float | None:
    if any(leg.allocated_value is None for leg in legs):
        return None
    return sum(leg.allocated_value for leg in legs if leg.allocated_value is not None)


def _compute_aggregate_pnl(legs: list[StrategyLeg]) -> float | None:
    if any(leg.allocated_pnl is None for leg in legs):
        return None
    return sum(leg.allocated_pnl for leg in legs if leg.allocated_pnl is not None)


def _is_option_complete(pos: Position) -> bool:
    return (
        pos.security_type == SecurityType.OPTION
        and pos.option_type is not None
        and pos.strike is not None
        and pos.expiration is not None
    )


def _format_short_long_explanation(short_pos: Position, long_pos: Position, same_strike: bool) -> str:
    """Format explanation with short-near/long-far convention."""
    assert short_pos.expiration is not None
    assert long_pos.expiration is not None
    assert short_pos.strike is not None
    assert long_pos.strike is not None

    if same_strike:
        return f"Short {short_pos.expiration} / Long {long_pos.expiration} at ${short_pos.strike:.2f}"
    else:
        return f"Short {short_pos.expiration} ${short_pos.strike:.2f} / Long {long_pos.expiration} ${long_pos.strike:.2f}"


def _build_phase_predicate(
    phase: _SpreadPhase,
    option_type: OptionType,
    ledger: _AllocationLedger
) -> Callable[[Position, Position], bool]:
    """Build predicate for a specific phase and option type with residual and expiry checks."""
    def phase_predicate(p1: Position, p2: Position) -> bool:
        # Must have opposite-sign residuals
        r1 = ledger.get_residual(p1.id)
        r2 = ledger.get_residual(p2.id)
        if r1 * r2 >= 0:
            return False

        # Must match option type and multiplier
        if p1.option_type != option_type or p2.option_type != option_type:
            return False
        if p1.multiplier != p2.multiplier:
            return False

        # Determine short/long by residual sign (negative = short, positive = long)
        if r1 < 0:
            short_pos, long_pos = p1, p2
        else:
            short_pos, long_pos = p2, p1

        assert short_pos.expiration is not None
        assert long_pos.expiration is not None
        assert short_pos.strike is not None
        assert long_pos.strike is not None

        if phase == _SpreadPhase.CALENDAR:
            # Same strike, short expiry < long expiry
            return (short_pos.strike == long_pos.strike
                    and short_pos.expiration < long_pos.expiration)
        elif phase == _SpreadPhase.DIAGONAL:
            # Different strikes, short expiry < long expiry
            return (short_pos.strike != long_pos.strike
                    and short_pos.expiration < long_pos.expiration)
        elif phase == _SpreadPhase.VERTICAL:
            # Same expiry, different strikes
            return (short_pos.expiration == long_pos.expiration
                    and short_pos.strike != long_pos.strike)
        return False

    return phase_predicate


def _find_ambiguous_connected_component(
    candidates: list[Position],
    predicate: Callable[[Position, Position], bool]
) -> set[str]:
    """Find all positions in connected components containing ambiguity."""
    # Build eligibility graph
    graph: dict[str, set[str]] = defaultdict(set)
    for i, p1 in enumerate(candidates):
        for p2 in candidates[i+1:]:
            if predicate(p1, p2):
                graph[p1.id].add(p2.id)
                graph[p2.id].add(p1.id)

    # Find nodes with multiple partners
    ambiguous_nodes = {pid for pid, partners in graph.items() if len(partners) > 1}
    if not ambiguous_nodes:
        return set()

    # BFS to find full connected component
    blocked = set()
    to_visit = list(ambiguous_nodes)
    while to_visit:
        current = to_visit.pop()
        if current in blocked:
            continue
        blocked.add(current)
        for neighbor in graph.get(current, []):
            if neighbor not in blocked:
                to_visit.append(neighbor)
    return blocked


def _emit_pair_strategy(
    pos1: Position, pos2: Position,
    qty1: float, qty2: float,
    strategy_type: StrategyType,
    name: str, explanation: str,
    ledger: _AllocationLedger
) -> Strategy:
    """Emit a two-leg strategy after ledger allocation."""
    allocations = [(pos1.id, qty1), (pos2.id, qty2)]
    for pid, qty in allocations:
        ledger.allocate(pid, qty)
    legs = _make_legs(allocations, ledger)
    return Strategy(
        id=_make_strategy_id(strategy_type, [pos1.id, pos2.id]),
        account_id=pos1.account_id,
        symbol=pos1.symbol,
        currency=pos1.currency,
        strategy_type=strategy_type,
        quantity=min(abs(qty1), abs(qty2)),
        name=name,
        legs=legs,
        market_value=_compute_aggregate_value(legs),
        unrealized_pnl=_compute_aggregate_pnl(legs),
        confidence=1.0,
        explanation=explanation,
    )


def _emit_single_strategy(
    pos: Position, residual: float, strategy_type: StrategyType,
    name: str, explanation: str, confidence: float, ledger: _AllocationLedger
) -> Strategy:
    """Emit a single-leg strategy."""
    allocations = [(pos.id, residual)]
    ledger.allocate(pos.id, residual)
    legs = _make_legs(allocations, ledger)
    return Strategy(
        id=_make_strategy_id(strategy_type, [pos.id]),
        account_id=pos.account_id,
        symbol=pos.symbol,
        currency=pos.currency,
        strategy_type=strategy_type,
        quantity=abs(residual),
        name=name,
        legs=legs,
        market_value=_compute_aggregate_value(legs),
        unrealized_pnl=_compute_aggregate_pnl(legs),
        confidence=confidence,
        explanation=explanation,
    )


def _match_pairs_with_predicate(
    candidates: list[Position],
    predicate: Callable[[Position, Position], bool],
    blocked: set[str],
    ledger: _AllocationLedger,
    strategy_type: StrategyType,
    name_fn: Callable[[str, OptionType, float], str],
    phase: _SpreadPhase,
) -> list[Strategy]:
    """Match pairs using predicate, respecting blocked set and ledger guard."""
    strategies = []
    matched = set()

    for p1 in candidates:
        if p1.id in matched or p1.id in blocked:
            continue
        r1 = ledger.get_residual(p1.id)
        if abs(r1) < 1e-9:
            continue

        for p2 in candidates:
            if p2.id == p1.id or p2.id in matched or p2.id in blocked:
                continue
            r2 = ledger.get_residual(p2.id)
            if abs(r2) < 1e-9:
                continue

            if predicate(p1, p2):
                # Predicate already checked opposite signs, determine short/long
                if r1 < 0:
                    short_pos, long_pos = p1, p2
                    qty_short = min(abs(r1), abs(r2))
                    qty1, qty2 = -qty_short, qty_short
                else:
                    short_pos, long_pos = p2, p1
                    qty_short = min(abs(r1), abs(r2))
                    qty1, qty2 = qty_short, -qty_short

                if not (ledger.can_allocate(p1.id, qty1) and ledger.can_allocate(p2.id, qty2)):
                    continue

                assert short_pos.option_type is not None
                explanation = _format_short_long_explanation(
                    short_pos, long_pos,
                    same_strike=(phase == _SpreadPhase.CALENDAR)
                )

                strategy = _emit_pair_strategy(
                    p1, p2, qty1, qty2,
                    strategy_type,
                    name_fn(p1.symbol, short_pos.option_type, qty_short),
                    explanation,
                    ledger
                )
                strategies.append(strategy)
                matched.add(p1.id)
                matched.add(p2.id)
                break

    return strategies


def recognize_strategies(positions: list[Position]) -> list[Strategy]:
    """Recognize strategies from positions with graph ambiguity detection and ledger guard."""
    if not positions:
        return []

    ids = [p.id for p in positions]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate position IDs: {[i for i in ids if ids.count(i) > 1]}")

    sorted_positions = sorted(positions, key=_deterministic_sort_key)
    ledger = _AllocationLedger(sorted_positions)

    # Partition by (account, symbol, currency)
    partitions: dict[tuple[str, str, str], list[Position]] = defaultdict(list)
    for p in sorted_positions:
        partitions[(p.account_id, p.symbol, p.currency)].append(p)

    all_strategies = []

    for (_account_id, symbol, _currency), group in partitions.items():
        # Extension hook: stock coverage spreads (Task 3)
        from packages.strategy_engine.coverage import apply_coverage_strategies

        # Separate by multiplier
        multiplier_groups: dict[float, list[Position]] = defaultdict(list)
        stock_positions = []
        for p in group:
            if p.security_type == SecurityType.OPTION:
                multiplier_groups[p.multiplier].append(p)
            else:
                stock_positions.append(p)

        # Global blocked set for this partition
        blocked: set[str] = set()

        # Apply coverage strategies first
        coverage_strategies, coverage_blocked = apply_coverage_strategies(
            stock_positions, [p for mult_opts in multiplier_groups.values() for p in mult_opts],
            ledger, blocked, symbol
        )
        all_strategies.extend(coverage_strategies)

        # Process each multiplier group independently
        for opt_group in multiplier_groups.values():
            # Filter complete options with nonzero residuals
            phase_opt_group = [p for p in opt_group
                               if _is_option_complete(p)
                               and abs(ledger.get_residual(p.id)) > 1e-9
                               and p.id not in blocked]

            # Process phases in priority order: CALENDAR -> DIAGONAL -> VERTICAL
            for phase in _SpreadPhase:
                candidates = [p for p in phase_opt_group if p.id not in blocked]
                if not candidates:
                    continue

                # Process both CALL and PUT for this phase
                for option_type in [OptionType.CALL, OptionType.PUT]:
                    phase_candidates = [p for p in candidates if p.option_type == option_type]
                    if len(phase_candidates) < 2:
                        continue

                    # Build predicate for this phase + option type
                    predicate = _build_phase_predicate(phase, option_type, ledger)

                    # Find ambiguities for this specific phase + option type
                    phase_blocked = _find_ambiguous_connected_component(phase_candidates, predicate)
                    blocked.update(phase_blocked)

                    # Recompute candidates excluding newly blocked
                    phase_candidates = [p for p in phase_candidates if p.id not in blocked]

                    # Determine strategy type and name format
                    if phase == _SpreadPhase.CALENDAR:
                        strategy_type = (StrategyType.CALENDAR_CALL if option_type == OptionType.CALL
                                       else StrategyType.CALENDAR_PUT)
                        def make_calendar_name(sym: str, _opt: OptionType, q: float) -> str:
                            return f"{sym} Calendar {_opt.value.title()} ×{int(q)}"
                        name_fn = make_calendar_name
                    elif phase == _SpreadPhase.DIAGONAL:
                        strategy_type = StrategyType.DIAGONAL
                        def make_diagonal_name(sym: str, _opt: OptionType, q: float) -> str:
                            return f"{sym} Diagonal {_opt.value.title()} ×{int(q)}"
                        name_fn = make_diagonal_name
                    else:  # VERTICAL
                        strategy_type = (StrategyType.VERTICAL_CALL if option_type == OptionType.CALL
                                       else StrategyType.VERTICAL_PUT)
                        def make_vertical_name(sym: str, _opt: OptionType, q: float) -> str:
                            return f"{sym} Vertical {_opt.value.title()} ×{int(q)}"
                        name_fn = make_vertical_name

                    # Match pairs for this phase + option type
                    all_strategies.extend(_match_pairs_with_predicate(
                        phase_candidates, predicate, blocked, ledger,
                        strategy_type, name_fn, phase
                    ))

            # Singles for this multiplier group
            for pos in opt_group:
                if not _is_option_complete(pos) or pos.id in blocked:
                    continue
                residual = ledger.get_residual(pos.id)
                if abs(residual) < 1e-9:
                    continue

                assert pos.option_type is not None
                assert pos.strike is not None
                assert pos.expiration is not None

                if residual > 0:
                    st = StrategyType.LONG_CALL if pos.option_type == OptionType.CALL else StrategyType.LONG_PUT
                    prefix = "Long"
                else:
                    st = StrategyType.SHORT_CALL if pos.option_type == OptionType.CALL else StrategyType.SHORT_PUT
                    prefix = "Short"

                all_strategies.append(_emit_single_strategy(
                    pos, residual, st,
                    f"{symbol} {prefix} {pos.option_type.value.title()} ×{int(abs(residual))}",
                    f"${pos.strike:.2f} expiring {pos.expiration}",
                    1.0, ledger
                ))

        # Stock
        for pos in stock_positions:
            residual = ledger.get_residual(pos.id)
            if abs(residual) > 1e-9:
                all_strategies.append(_emit_single_strategy(
                    pos, residual, StrategyType.STOCK,
                    f"{symbol} Stock",
                    f"{residual:+.2f} shares",
                    1.0, ledger
                ))

        # Emit unmatched for blocked and incomplete
        for pos in group:
            if pos.id in blocked or (pos.security_type == SecurityType.OPTION and not _is_option_complete(pos)):
                residual = ledger.get_residual(pos.id)
                if abs(residual) > 1e-9:
                    if pos.id in blocked:
                        expl = "Ambiguous matching candidates"
                    else:
                        expl = "Incomplete option terms"
                    all_strategies.append(_emit_single_strategy(
                        pos, residual, StrategyType.UNMATCHED,
                        f"{symbol} Unmatched",
                        expl,
                        0.0, ledger
                    ))

    return sorted(all_strategies, key=lambda s: s.id)
