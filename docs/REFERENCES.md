# Reference inspection

Inspected before implementation on 2026-09-27 (local date). These repositories are architecture references, not specifications. No substantial code or UI assets copied. Missing root licenses are not permission to reuse source.

## ib_async

Reference: https://github.com/ib-api-reloaded/ib_async

Inspected revision: `ab629f34c1823ea4c1542f32f07377208a86bdfd`. License: BSD-2-Clause.

Inspected ib_async/ib.py connection, readonly flag, account filtering, positions/portfolio/accountSummary and portfolio events. Future adapter must manage reconnect and stale values. readonly skips order synchronization but does not remove library mutation methods; encapsulation and Gateway settings are both necessary.

## ibkr-options-stock-trader

Reference: https://github.com/Hoary-Stock/ibkr-options-stock-trader

Inspected revision: `054faa667eb6b43be44eaec525103f5ee0545551`. License: No root license found.

Inspected README and widgets/strategy_window.py: local _open_combos JSON save/load retains combo grouping absent from broker holdings. Adopt concept only; defer persisted manual overrides.

## IB-Tracker

Reference: https://github.com/parrondo/IB-Tracker

Inspected revision: `537967af27cc81cc9512b3a2d300a26f802c52a0`. License: MIT.

Inspected Database/trade.h: Trade → Transaction → Legs hierarchy, original/open quantity, back pointers for close/roll. Current holdings cannot reconstruct this history; keep source IDs for future reconciliation.

## investing-platform

Reference: https://github.com/imyjimmy/investing-platform

Inspected revision: `58c8c9132f5c633de8d73cac544d8eac491301f0`. License: No root license found.

Inspected React folder structure, useAccountData hook and API transport: separate typed API access, account selection and UI components. Our implementation excludes its execution and wider research functionality.

## ib_dashboard

Reference: https://github.com/yjthay/ib_dashboard

Inspected revision: `7b1f70772dd9a365e8efcbc238519ac2c51684ec`. License: No root license found.

Inspected main.py, README and requirements: simple data-to-dashboard layering, but obsolete Dash dependencies and cloud sample documentation are not suitable foundations for this draft.
