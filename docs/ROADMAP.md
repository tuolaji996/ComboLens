# ComboLens roadmap

**Ongoing project — not a finished trading product. Viewer only.**

“IBKR gives me legs. ComboLens tells me what I actually own.”

The central questions are: Which strategies do these legs form? What do I own? How much has each strategy made or lost since I opened it?

## Working draft

- Normalized mock positions, conservative strategy recognition, read-only API.
- Desktop/mobile Strategies, Underlyings and Raw Positions views.
- Current unrealized P&L per strategy.
- Explicitly mock opening-history summaries and separate net-since-opening preview; unavailable states where history is absent.

## Next: trustworthy strategy profit

1. Read IBKR positions, executions, commissions and account metrics through an encapsulated read-only provider.
2. Persist lifecycle identity independently of the current leg composition. Adding a leg, changing size, rolling or partially closing must not silently reset P&L or attach another trade's history.
3. Reconcile opening cash flows, closing proceeds, cost basis, realized P&L and fees. Establish fee-inclusive versus fee-exclusive broker conventions so fees cannot be charged twice.
4. Separate unrealized, realized, daily and net-since-opening P&L; keep missing history explicit. Handle fully closed strategies and currency consistently.
5. Let the user review/override inferred groupings and preserve an audit trail.
6. Validate reconciliation against a paper account and broker statements before claiming real-account strategy performance.

## Then

- Snapshot persistence and freshness/reconnect indicators.
- Multiple accounts, adjusted deliverables and explicit FX policy.
- More strategy shapes and improved ambiguity review.
- PWA suitability and production security only after the data model is verified.

No order submission, modification, cancellation or exercise capability is planned.
