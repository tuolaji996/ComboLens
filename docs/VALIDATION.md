# Draft V0.1 validation log

## Workflow
- Codex inspected the initially empty Git repository and five reference repositories before writing DRAFT_PLAN.md.
- Claude implementation uses native PAL clink, implementer role. Returned metadata reports `claude-opus-5-5`; this identifier alone does not independently verify backend identity.
- Claude owns implementation in a restricted staging workspace; Codex reviews and copies accepted milestones into this repository.
- First model pass: 39 unit tests passed; strict mypy passed. Lint reported modernization and overly broad exception assertions. Review also identified fixture arithmetic and API naming corrections. Sent these to Claude before proceeding.

## Acceptance evidence
Completed. See FINAL_REPORT.md for the acceptance matrix and deliverables.

## Models milestone
- 45 tests passed after model corrections; strict mypy passed.
- Codex directly recomputed fixture account totals from position values (small numeric correction): net liquidation 115777.94, unrealized P&L 705.30. UNH calendar 1464.00 / -34.70.
- Remaining unused test variable assigned to Claude in matcher task.
- Model choices: strategy legs reference position_id and carry allocated_quantity/value/pnl; UI joins these to raw positions. Strategy totals use market_value/unrealized_pnl and numeric confidence.

## Matcher review in progress
- First Claude matcher task exceeded the 240-second tool limit; incomplete output stayed in staging.
- Codex identified invalid imports/model fields, incorrect ambiguity propagation, reverse-calendar classification and phase ordering. Focused correction tasks assigned to Claude.
- Codex made minor test maintenance edits: current field names and fixture paths, correct UNH stock quantity (2), and expectations for multiplier-separated singles and explicit QQQ ambiguity.

## Option matcher milestone
- 71 combined unit tests passed. Strict mypy passed in four source files.
- Independent Codex check: 400 seeded randomized option portfolios passed per-source quantity conservation, strategy ID uniqueness, temporal orientation for calendars/diagonals, and input permutation stability.
- Remaining style-only lint issues assigned to Claude with stock coverage milestone.
- Missing metadata stays unmatched; reverse calendars remain individual options. Candidate ambiguity evaluated at each tier using current residuals.

## Complete strategy engine milestone
- 96 combined tests passed, strict mypy passed, Ruff passed.
- Independent Codex check: 500 seeded mixed stock/option portfolios passed per-source sign/quantity conservation, aggregate market-value conservation, strategy ID uniqueness and permutation stability.
- Required fixture outputs confirmed: UNH calendar ×3 (1464.00), stock ×2 (753.94); DRAM collar ×1 (5805.00); NVDA/SPMO long calls ×1; QQQ and XYZ unmatched.
- Claude coverage correction hit the tool time limit after writing files. Codex removed two duplicate `else` tokens and renamed unused loop variables; then all checks passed.

## API milestone
- 113 Python tests passed; strict mypy (8 source files) and Ruff passed.
- Editable installation succeeded; FastAPI started at 127.0.0.1:8000.
- OpenAPI has exactly five portfolio paths, each GET-only. Unsupported writes return 405 on those routes.
- Tests cover raw fixture order, copy isolation, timestamp stability, null propagation, no double counting, live-provider explicit failure and provider configuration errors.
- Codex corrected small test field-name errors and removed unused type-ignore comments after Claude's API correction.
- One upstream Starlette warning deprecates its httpx TestClient integration; no test failures.

## Parallel integration
- User explicitly authorized more Claude assistants. Frontend behavior, CSS polish, and browser-test/compose work assigned in parallel with disjoint file ownership.
- Codex added pnpm allowBuilds configuration for esbuild's required install script after the initial pnpm install rejected ignored build scripts.

## Final acceptance
- Python: 116 tests passed (one upstream Starlette/httpx deprecation warning).
- Strict mypy: passed for 8 source files. Ruff: passed after import sorting.
- Frontend: TypeScript check passed; final Vite production build passed (JS approximately 240 kB / 74 kB gzip).
- Browser: all scenarios passed against running local servers at 1440×1100, 390×844, and 375×812.
- Exact fixture positions/order, nine strategy cards, UNH/DRAM/SPMO/NVDA, signed legs, Pacific-time expiration dates, search/empty/recovery states, raw native JSON details and all-tab overflow checked.
- Mobile search width asserted usable; final mobile metrics compacted and screenshots refreshed.
- Codex visually inspected desktop and mobile screenshots. Unexpected page/console errors fail the browser suite; none occurred.
- Claude fixed source-ID delimiter collisions with canonical SHA256 IDs; three regression tests pass.
- Docker Compose parsed and localhost port bindings validated. Docker not installed here, so container execution is unverified.
- No live Gateway used. V0.2 not started.
- Backend and frontend left running on localhost; browser panel opening queued.

Final run commands from repository root: `python -m pytest`, `python -m mypy packages apps/api`, `python -m ruff check packages apps/api tests`, `pnpm --dir apps/web typecheck`, `pnpm --dir apps/web build`, `pnpm --dir tests/browser test`. Local bundled Python/Node paths were used where system binaries were unavailable.

## ComboLens rename and profit-preview milestone

- Current validation: 136 Python tests passed; strict mypy passed for 9 source files; Ruff passed; TypeScript and Vite build passed.
- Browser acceptance additionally verifies ComboLens branding, distinct unrealized/net-since-opening totals, NVDA realized profit and fees, unavailable QQQ/XYZ totals, and expanded performance panels at both phone widths.
- All prior browser scenarios still pass. Updated desktop/mobile screenshots were visually reviewed.
- Claude implemented the new models, enrichment, mock history, frontend and focused tests. Codex corrected test reason-label expectations, added API consistency and unmatched-history regression checks, and extended browser verification.
- This completes the branding/profit-preview milestone only. Real execution history, commissions and lifecycle identity remain unfinished. See COMBOLENS_RELEASE_NOTES.md and ROADMAP.md.
