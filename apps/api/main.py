"""FastAPI main application."""

import os
from collections import defaultdict
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from apps.api.performance import enrich_strategies_with_performance
from apps.api.providers import (
    MockPortfolioProvider,
    PortfolioProvider,
)
from packages.portfolio_models.models import AccountMetrics, Position, Strategy, Underlying
from packages.strategy_engine import recognize_strategies


class StatusResponse(BaseModel):
    """Status endpoint response."""
    status: str
    ibkr_connected: bool
    data_source: str
    last_sync: str


def create_app(provider: PortfolioProvider | None = None) -> FastAPI:
    """Create FastAPI app with optional provider."""
    if provider is None:
        provider_type = os.getenv("PORTFOLIO_PROVIDER", "mock")
        if provider_type == "mock":
            provider = MockPortfolioProvider()
        elif provider_type == "ibkr":
            raise NotImplementedError("IBKR provider not yet implemented")
        else:
            raise ValueError(f"Invalid PORTFOLIO_PROVIDER: {provider_type}")

    app = FastAPI(title="ComboLens", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/status", response_model=StatusResponse)
    def get_status() -> dict[str, Any]:
        status = provider.get_status()
        return {
            "status": "ok",
            "ibkr_connected": status.ibkr_connected,
            "data_source": status.data_source,
            "last_sync": status.last_sync,
        }

    @app.get("/api/v1/positions", response_model=list[Position])
    def get_positions() -> list[Position]:
        snapshot = provider.get_snapshot()
        return snapshot.positions

    @app.get("/api/v1/strategies", response_model=list[Strategy])
    def get_strategies() -> list[Strategy]:
        snapshot = provider.get_snapshot()
        strategies = recognize_strategies(snapshot.positions)
        return enrich_strategies_with_performance(strategies, snapshot)

    @app.get("/api/v1/underlyings", response_model=list[Underlying])
    def get_underlyings() -> list[Underlying]:
        snapshot = provider.get_snapshot()
        strategies = recognize_strategies(snapshot.positions)
        enriched_strategies = enrich_strategies_with_performance(strategies, snapshot)

        # Group by (account_id, symbol, currency)
        groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
            lambda: {"positions": [], "strategies": []}
        )

        for pos in snapshot.positions:
            key = (pos.account_id, pos.symbol, pos.currency)
            groups[key]["positions"].append(pos)

        for strat in enriched_strategies:
            key = (strat.account_id, strat.symbol, strat.currency)
            groups[key]["strategies"].append(strat)

        underlyings = []
        for (account_id, symbol, currency), group_data in groups.items():
            positions = group_data["positions"]
            strategies = group_data["strategies"]

            # Aggregate values from positions - require all values present
            net_value = None
            net_pnl = None
            underlying_price = None

            if positions:
                values = [p.market_value for p in positions]
                pnls = [p.unrealized_pnl for p in positions]
                prices = [p.underlying_price for p in positions if p.underlying_price is not None]

                if all(v is not None for v in values):
                    net_value = sum(values)
                if all(p is not None for p in pnls):
                    net_pnl = sum(pnls)
                underlying_price = prices[0] if prices else None

            underlyings.append(Underlying(
                account_id=account_id,
                symbol=symbol,
                currency=currency,
                positions=positions,
                strategies=strategies,
                net_value=net_value,
                net_pnl=net_pnl,
                underlying_price=underlying_price,
            ))

        return sorted(underlyings, key=lambda u: (u.account_id, u.symbol))

    @app.get("/api/v1/account", response_model=AccountMetrics)
    def get_account() -> AccountMetrics:
        snapshot = provider.get_snapshot()
        return snapshot.account

    return app


app = create_app()
