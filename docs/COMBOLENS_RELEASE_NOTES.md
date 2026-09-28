# ComboLens — branding and strategy-profit preview

**Status: ongoing draft. Not a production release.**

## Product direction

> IBKR gives me legs. ComboLens tells me what I actually own.

ComboLens is a strategy-aware interpretation layer for IBKR, with profit and loss presented at the strategy level. The user requested both current unrealized P&L and net P&L since opening, shown separately.

## Changes

- Project/UI/API/package branding changed to ComboLens; the README and roadmap explicitly describe the project as unfinished.
- Strategy cards distinguish market value, unrealized P&L and net since opening.
- Expanded strategies show an opening timestamp, realized P&L and fees.
- Five synthetic opening-history summaries demonstrate the calculation. They are labeled **Mock history**.
- Strategy history is matched using account, currency and the exact signed allocated-leg signature. Optional strategy IDs must agree when supplied. Changed allocation quantities do not inherit an old summary.
- Unmatched groups, missing/incomplete/duplicate history, incompatible fee treatment and unknown unrealized P&L produce an unavailable total.
- The five API routes remain GET-only; raw normalized positions are unchanged.

## Calculation and mock examples

`Net since opening = unrealized P&L + realized P&L − lifecycle fees`

This applies only when the supplied history is complete and explicitly states that both unrealized and realized P&L exclude the recorded fees. Otherwise the result remains unavailable to avoid double-counting costs.

| Strategy | Unrealized | Realized | Fees | Net since opening |
| --- | ---: | ---: | ---: | ---: |
| UNH Calendar Call ×3 | −$34.70 | $0.00 | $3.90 | −$38.60 |
| DRAM Collar ×1 | $175.00 | $0.00 | $1.30 | $173.70 |
| SPMO Long Call ×1 | $125.00 | $0.00 | $0.65 | $124.35 |
| NVDA Long Call ×1 | $320.00 | $45.00 | $1.95 | $363.05 |
| UNH Stock ×2 | $15.00 | $0.00 | $0.00 | $15.00 |

These figures are synthetic examples, not imported account performance. Realized amounts and fees are supplied explicitly; they are not reconstructed from current market value. No percentage return is presented without a defined capital basis.

## Remaining work

The current exact-signature summaries are a mock-only preview, not a persistent execution ledger. Trustworthy live performance still needs broker executions and commissions, fee-convention reconciliation, persistent lifecycle identity across size changes/partial closes/rolls, closed strategy tracking and user-confirmed grouping. See ROADMAP.md.

## Ownership

Claude implemented the performance models, API enrichment, fixture summaries, frontend presentation and focused tests. Codex specified the accounting boundary, reviewed and integrated the changes, ran validation, updated project documentation, and prepared GitHub publication.

## Verification

- 136 Python tests passed, including 20 performance tests for arithmetic, matching boundaries, missing history, validation, API consistency and raw-position preservation.
- Strict mypy passed for 9 source files; Ruff passed.
- TypeScript and Vite production build passed.
- Browser acceptance passed at 1440×1100, 390×844 and 375×812, including separate UNH/NVDA profit figures, realized/fee breakdown, unavailable totals, mock labeling, GET-only traffic, error recovery and expanded mobile layout.
- Desktop and mobile screenshots refreshed and visually reviewed.
- One upstream Starlette/httpx TestClient deprecation warning remains. Docker execution and live IBKR integration remain unverified.
