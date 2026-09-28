# Browser Acceptance Tests

Playwright-based tests for IBKR Viewer UI contracts.

## Prerequisites

- Node.js 22+ with pnpm installed
- Running API on http://127.0.0.1:8000
- Running web dev server on http://127.0.0.1:5173

## Installation

From the repository root:

```sh
cd tests/browser
pnpm install
pnpm exec playwright install chromium
```

## Run Tests

```sh
pnpm test
```

Set custom URLs if needed:

```sh
BASE_URL=http://localhost:5173 API_URL=http://localhost:8000 pnpm test
```

## What's Tested

- Three viewport sizes: desktop 1440×1100, mobile 390×844 and 375×812
- No document or main overflow across all three tabs
- Strategies tab selected by default
- Strategy cards for UNH Calendar Call ×3, DRAM Collar ×1, NVDA/SPMO Long Call visible
- Expand UNH and verify -3/+3 allocated legs
- Search filters by symbol; mobile search has usable width
- Empty search and clear
- Underlyings and Raw Positions tabs work
- Raw details/summary shows JSON normalized record
- Error state shown when API fails; recovery after refresh/reload
- Unexpected browser exceptions and console errors fail the test
- Network requests are GET-only
- API positions match fixture count and fields

Screenshots saved to `docs/screenshots/` after tests.
