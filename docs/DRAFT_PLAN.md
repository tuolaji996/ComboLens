# ComboLens — initial viewer draft plan

Status: Draft V0.1 implemented and validated. Viewer only. See FINAL_REPORT.md and VALIDATION.md.

## Architecture and scope
React + TypeScript + Vite → GET-only FastAPI → PortfolioProvider → normalized snapshot. The strategy engine is pure Python over normalized Pydantic models, with no broker dependency. Mock mode is complete; the IBKR provider is an explicitly unavailable skeleton. No broker mutation capability, order objects, or trading endpoints. Local development only. No production authentication, databases, native apps, or deployment automation.

## Repository structure
- apps/api/: FastAPI app, providers, provider configuration
- apps/web/: React UI, typed API client, responsive styles
- packages/portfolio_models/: normalized models
- packages/strategy_engine/: deterministic allocation and matchers
- fixtures/: fixed mock snapshot and ambiguity examples
- tests/: model, matcher, API and safety regression tests
- docs/: plan, reference findings, validation report and screenshots
- pyproject.toml, docker-compose.yml, README.md, .gitignore

## Normalized models
Position: stable id, account_id, symbol, currency, security_type (STOCK/OPTION), signed quantity, optional option_type/strike/expiration, positive multiplier, optional market_price/market_value/unrealized_pnl, underlying_price. Option contracts require complete terms to participate in matching; incomplete terms are preserved as unmatched. Stocks use multiplier 1; option counts must be integral. Reject nonfinite quantities and prices, duplicate ids at snapshot/engine boundary. Missing valuations remain null, never zero. Numeric JSON values use finite floats for this draft, with tolerance-based conservation tests; production money precision is deferred.

Strategy: deterministic id, symbol, strategy_type, positive quantity, name, allocated legs (source position id + signed allocated quantity, prorated values), aggregate value/P&L, confidence, explanation. Types: COLLAR, COVERED_CALL, PROTECTIVE_PUT, CALENDAR_CALL/PUT, DIAGONAL, VERTICAL_CALL/PUT, LONG_CALL/PUT, SHORT_CALL/PUT, STOCK, UNMATCHED. Confidence is rule certainty, never probability or evidence of original trade intent.

Snapshot: fixed as_of timestamp, account metrics, raw positions. Account includes currency, net_liquidation, cash, daily_pnl, unrealized_pnl, maintenance_margin, excess_liquidity, buying_power. Underlying summary groups original positions and strategies, net value/P&L, price.

## Matching precedence and allocation
Partition by account, symbol and currency, then require identical option multipliers. Stable sorting makes results independent of input ordering. Consume from an immutable-source residual quantity ledger; never modify input. Precedence: collar → covered call → protective put → calendar → diagonal → vertical → singles → stock/unmatched. Stock protections take priority to preserve coverage; calendars use identical strikes; diagonals differ in strike and expiry; verticals share expiry. Calendar/diagonal recognize near short + far long only in V0.1; reverse patterns remain singles with explanation. Collar requires same option expiry and put strike <= call strike. Coverage uses actual multiplier, including non-100 contracts. Allocate minimum whole strategy units; leave all excess quantities represented. Ambiguous competing eligible pairings at a matching tier remain explicitly unmatched rather than inferring intent. Conservative ambiguity detection and its limits must be documented. Unknown option terms remain unmatched. Stable ids derive from type and allocated sources. Aggregated value/P&L are null if any contributing value is unknown.

## Provider boundary and IBKR path
PortfolioProvider exposes only read snapshot/status operations. Mock provider loads fixed JSON once and returns independent data. IBKRPortfolioProvider cannot connect in V0.1 and must fail explicitly if selected, never silently fall back to mock. Future implementation wraps private ib_async IB, connectAsync(readonly=True), account-filtered positions/portfolio/accountSummary, and portfolio/connection events. Gateway Read-Only API setting is also required; readonly=True alone is not a security boundary. No raw IB object reaches API clients. Future reconnection, subscriptions, timeouts, contract normalization and account selection require paper-account validation.

## REST contract
All endpoints under /api/v1, GET only; OpenAPI documents response models.
- /status → {status, ibkr_connected:false, data_source:"mock", last_sync: ISO timestamp}
- /positions → Position[] in original normalized order
- /strategies → Strategy[] including stock and unmatched residuals
- /underlyings → Underlying[]
- /account → AccountMetrics
Errors must be visible, with no fabricated successful fallback. CORS limited to local frontend origin. Browser uses same-origin Vite proxy in development; provider access only through backend.

## WebSocket contract (future, not implemented)
Proposed /api/v1/ws publishes server-only {type:"snapshot", schema_version:1, sequence, as_of, data:{account,positions,strategies,underlyings,status}} and {type:"status",...}. Atomic snapshots, reconnect via REST resync, no broker commands. V0.1 uses initial REST fetch and manual refresh only.

## UI structure
Modern light brokerage dashboard, deep navy typography, warm white background, restrained teal accent. Header with custom typographic mark, Draft V0.1 and viewer-only badge; Gateway offline / mock label always visible. Large portfolio value, daily P&L and compact liquidity metrics. Default Strategies tab, Underlyings and Raw Positions tabs. Symbol search, count, expandable leg cards with signed quantities and clear option dates. No pretend performance chart because no history exists. Responsive cards and tab controls at 390px and 375px; accessible labels/focus/keyboard interactions, loading/error/empty states, manual refresh. Raw positions must expose every normalized field via details/JSON, preserving source values. Show snapshot date clearly (September sample may be historical).

## Testing and acceptance
Unit tests: all 12 strategies, covered call ×1/×2, calendar ×3, partial matching, multiplier differences, fractional stock, null valuations, ambiguity, account/currency segregation, duplicate ids, permutation determinism, raw immutability, per-source signed quantity and value conservation. API tests verify five schemas, mock independence, same totals, only GET routes, unsupported writes rejected, IBKR explicit unavailability. Run pytest, Python type check/lint, TypeScript type check, production build. Browser checks desktop and iPhone dimensions, all tabs, expansion, search, refresh, offline/error states, overflow and screenshots. No live Gateway required.

Acceptance: local backend/frontend run; UNH Calendar Call ×3 plus Stock ×2; DRAM Collar ×1; SPMO/NVDA Long Call ×1; unmatched visible; Raw/Underlyings correct; no duplicate allocation or trading endpoints; tests/types/build pass; README and final report complete. Stop at V0.1.

## Claude/Codex ownership and milestones
Codex inspects references, writes this plan, reviews each milestone, runs checks, integrates and documents evidence. Claude is the primary code writer through PAL clink using the configured Claude route. Implementation uses an isolated staging directory; only accepted files are copied into the repository. No overlapping edits.
1. Models, mock fixtures, Python project setup and model tests.
2. Allocation engine, all matchers, strategy tests.
3. Mock/IBKR skeleton providers, FastAPI endpoints and API tests.
4. React UI and typed REST integration, responsive styles.
5. Focused fixes following review; development packaging and README.
6. Codex acceptance, screenshots, final report; no automatic V0.2.

## Known limitations and risks
Holdings cannot prove original strategy intent or rolled-trade history; local grouping metadata and snapshot persistence are future work. Adjusted option deliverables need more than a numeric multiplier; unsupported contracts must not be guessed. Option market permissions, delayed/stale data, exchange/currency differences, account segregation, assignment/exercise and reconnect reconciliation need live testing later. Fixed mock prices are illustrative, not current quotes. Floating-point sums use tolerance in draft. No P&L analytics, Greeks, tax lots, FX conversion, live connection or persisted manual overrides. Performance chart omitted deliberately because there is no historical series.
