# ComboLens — ongoing project

User direction: rename/publish the unfinished project as ComboLens. “IBKR gives me legs. ComboLens tells me what I actually own.” Emphasize strategy-level profit, displaying current unrealized P&L and net P&L since opening separately.

## This milestone
- Brand the UI/API/package metadata and README as ComboLens. Preserve existing recognition and read-only boundaries.
- Retain existing unrealized_pnl meaning. Add an optional performance object with explicitly supplied lifecycle summaries, never infer realized gains, fees or opening date from current positions.
- Mock snapshot can include clearly labeled synthetic history summaries keyed by deterministic strategy ID, account/currency and exact allocated-leg quantities. Missing, incomplete, mismatched or ambiguous history returns unavailable, never zero by default.
- Net since opening = realized P&L + current unrealized P&L − lifecycle fees, only when history states complete and P&L excludes those fees. No return percentage without a defined capital basis.
- Expose the same enriched strategy objects in strategies and underlyings. Preserve raw normalized positions and five GET-only routes.
- Test arithmetic, missing values/history, partial allocation mismatch, history isolation and UI separation. Refresh screenshots.
- Create private tuolaji996/ComboLens GitHub repository and push the reviewed draft with unfinished work explicit. No production release or deployment.

## Future work
Live broker connection, execution/commission reconciliation, persistent lifecycle IDs, opening/closing/partial-close/roll history, manual group overrides, daily vs inception P&L, and snapshot persistence remain unfinished. Mock lifecycle summaries prove presentation and arithmetic only; they do not constitute a transaction ledger.

Claude owns implementation in isolated staging; Codex owns architecture, validation, docs and GitHub integration. Backend and frontend work use disjoint files in parallel.
