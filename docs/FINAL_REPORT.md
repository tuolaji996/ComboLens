# Initial strategy-viewer milestone report

Historical milestone report: the initial viewer prototype was completed before the project was named **ComboLens**. The overall project remains unfinished. See COMBOLENS_RELEASE_NOTES.md and ROADMAP.md for current scope.

## Delivery and local access

- Web: http://127.0.0.1:5173
- API documentation: http://127.0.0.1:8000/docs
- Current mock snapshot: September 14, 2026, 16:00 UTC.
- Mock portfolio value: $115,777.94; cash: $100,000.00; unrealized P&L: $705.30.
- 12 raw normalized positions → 9 strategy/stock/unmatched records across 6 underlyings.
- Backend and frontend were left running on localhost for review. Restart instructions are in README.md.

## What Claude implemented

Claude wrote the normalized Pydantic models and fixture; residual allocation engine and all twelve strategy recognizers; stock-coverage module; provider protocol, mock provider and explicit IBKR skeleton; FastAPI routes; React/TypeScript application, API client and CSS; unit/API tests, browser acceptance script, and development Compose configuration. Focused Claude correction tasks addressed review findings. At the user's request, frontend behavior, visual polish and browser-test/packaging assistants worked in parallel with separate file ownership.

PAL metadata reported `claude-opus-5-5` throughout successful calls. A reported identifier alone does not independently verify backend identity. Some implementation calls exceeded the tool's 240-second limit; partial files stayed in staging until reviewed and validated.

## What Codex changed directly

Codex inspected the empty repository and all five requested references before writing the plan; defined contracts and acceptance criteria; reviewed Claude's files; ran tests, type checks, lint, browser checks and randomized allocation checks; integrated accepted milestones; and wrote the README, reference notes and final reports.

Small direct corrections included fixture account arithmetic; stale test field names/fixture references and expectations; duplicate `else` tokens left by an interrupted edit; unused imports/variables; pnpm's explicit esbuild build allowance and package-manager pin; and small UI integration fixes for badge conditions, raw native details, stock quantity labels, currency/source labels, composition labels, mobile search width and compact mobile metrics. Browser test corrections use the actual API strategy count and precise existing UI locators. The substantive implementation remained Claude's work.

## Final repository structure

```text
/
├── apps/
│   ├── api/
│   │   ├── main.py                 # Five typed GET routes and aggregation
│   │   └── providers.py            # Read-only protocol, mock and IBKR skeleton
│   └── web/
│       ├── src/
│       │   ├── App.tsx             # Strategies / Underlyings / Raw Positions
│       │   ├── App.css             # Desktop and mobile styling
│       │   ├── api.ts              # Typed REST access, timeout/error handling
│       │   ├── types.ts
│       │   └── main.tsx
│       ├── package.json
│       ├── pnpm-lock.yaml
│       ├── pnpm-workspace.yaml
│       ├── tsconfig.json
│       ├── vite.config.ts
│       └── index.html
├── packages/
│   ├── portfolio_models/models.py
│   └── strategy_engine/
│       ├── __init__.py             # Ledger, option matching, stable IDs
│       └── coverage.py             # Collar, covered call, protective put
├── fixtures/mock_portfolio.json
├── tests/
│   ├── test_models.py
│   ├── test_strategies.py
│   ├── test_coverage.py
│   ├── test_strategy_ids.py
│   ├── test_api.py
│   └── browser/                    # Playwright acceptance and lockfile
├── docs/
│   ├── DRAFT_PLAN.md
│   ├── REFERENCES.md
│   ├── VALIDATION.md
│   ├── FINAL_REPORT.md
│   └── screenshots/
├── pyproject.toml
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── README.md
```

## Architecture

React fetches the five versioned REST resources through FastAPI. FastAPI reads a `PortfolioProvider` snapshot. The pure Python strategy engine consumes normalized positions and never depends on an IBKR session. The UI joins allocated strategy legs to their source IDs for auditability, and the raw view preserves the original records.

Matching partitions by account, symbol and currency and respects option multipliers. Precedence is collar, covered call, protective put, calendar, diagonal, vertical, single options, then remaining stock/unmatched. Each allocation reduces a residual ledger, preserving quantities and prorating value/P&L. Ambiguous competing candidates remain unmatched; missing values propagate as unknown. Strategy IDs use deterministic hashes to avoid delimiter collisions.

The provider surface contains only read methods. Portfolio OpenAPI paths contain GET operations only. No broker connection, order/exercise method, trading route or frontend broker access is implemented. A future push-only WebSocket snapshot contract is documented, but WebSockets and persistence are outside V0.1.

## Verification results

| Check | Result |
| --- | --- |
| Python unit/API suite | 116 passed |
| Strict mypy | Passed, 8 source files |
| Ruff | Passed |
| TypeScript type check | Passed |
| Vite production build | Passed |
| Editable Python install | Passed |
| Live local HTTP checks | All five endpoints returned 200 |
| Browser acceptance | Passed at 1440×1100, 390×844 and 375×812 |
| Mobile layout | No document/main horizontal overflow across all three tabs; usable search verified |
| Data audit | Browser API response exactly equals normalized fixture fields and order |
| Error handling | API abort produces alert; app recovers after requests are restored |
| Date display | UNH Oct 16 / Nov 20 preserved in America/Los_Angeles browser timezone |
| Read-only checks | Five GET-only portfolio paths; unsupported writes rejected; browser portfolio requests GET-only |
| Allocation stress checks | 400 option-only + 500 mixed seeded portfolios passed conservation/order checks |
| Compose | YAML and localhost bindings validated; Docker runtime unavailable, containers not run |

The browser suite also verifies default Strategies tab, all required examples, signed expanded legs, exact strategy-card count, search/empty results, underlying grouping, raw JSON details, and no unexpected browser errors. Screenshots were visually inspected after automation.

One upstream Starlette deprecation warning concerns its httpx TestClient integration; the tests pass. No live IBKR session was used.

## Strategy-recognition test matrix

| Strategy / case | Validation |
| --- | --- |
| Long Call | Unit tests; SPMO and NVDA fixtures; browser |
| Long Put | Four-single-options regression |
| Short Call | Singles and residual allocation tests |
| Short Put | Dedicated unit test and four-single-options regression |
| Covered Call | ×1, ×2; 10/100 multipliers; partial/fractional stock |
| Protective Put | Dedicated coverage test |
| Collar | Three-leg test, partial coverage, DRAM fixture/browser |
| Call Vertical | Same-expiry, different-strike test |
| Put Vertical | Dedicated test and signed orientation regression |
| Call Calendar | Basic and ×3 tests; UNH fixture/browser |
| Put Calendar | Dedicated quantity-2 test |
| Diagonal | Both strike directions and different expiry tests |
| Reverse calendar | Preserved as individual options |
| Ambiguity / incomplete terms | QQQ competing calendars, XYZ incomplete option, overlapping coverage |
| Unequal quantities | Partial strategy + residual, per-source conservation |
| Isolation | Account, currency and symbol boundaries |
| No duplication | Ledger checks, immutable raw input, per-source quantities/values, UI count |
| Determinism | Permuted input and collision-prone source ID regressions |

Required fixture results:

| Symbol | Result | Market value | Unrealized P&L |
| --- | --- | ---: | ---: |
| UNH | Calendar Call ×3 | $1,464.00 | −$34.70 |
| UNH | Stock ×2 | $753.94 | $15.00 |
| DRAM | Collar ×1 | $5,805.00 | $175.00 |
| SPMO | Long Call ×1 | $875.00 | $125.00 |
| NVDA | Long Call ×1 | $4,520.00 | $320.00 |

## Screenshots

- [Desktop overview](screenshots/desktop-overview.png)
- [Desktop expanded UNH calendar](screenshots/desktop-1440.png)
- [Full desktop](screenshots/desktop-full.png)
- [Mobile overview](screenshots/mobile-390.png)
- [Full mobile portfolio](screenshots/mobile-full.png)

## Known limitations and IBKR work remaining

The data is an illustrative historical snapshot; refreshing does not advance its timestamp. Holdings reveal structural relationships, not original trade intent, tax lots or roll history. The conservative matcher may leave human-recognizable combinations ungrouped, especially with multiple stock lots or competing candidates. Reverse calendar/diagonal patterns are not named as spreads. Adjusted deliverables and FX conversion are unsupported, and numeric arithmetic uses float tolerances.

No live quotes, Greeks, historical analytics, persisted snapshots, manual overrides, authentication or native apps are implemented. The draft is intended for localhost. The live provider deliberately fails rather than falling back silently.

Gateway integration still needs private `ib_async` wiring, explicit account selection, read-only connection/settings, contract normalization, market-data permissions, subscription cleanup, freshness indicators, timeouts, reconnect/resync and paper-account reconciliation. Broker risk metrics should continue to come from the provider rather than inferred strategy labels.

## Recommended V0.2 scope

1. A paper-account-validated read-only Gateway provider with freshness/reconnect states.
2. Local persisted snapshots and user-confirmed grouping overrides.
3. Better handling of ambiguous groups, adjusted contracts and multiple accounts.

V0.2 has not started. Production hardening, cloud infrastructure and native mobile development require separately agreed scope.
