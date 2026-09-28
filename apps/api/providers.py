"""Portfolio provider protocol and implementations."""

from pathlib import Path
from typing import Protocol

from packages.portfolio_models.models import Snapshot


class StatusModel:
    """Provider status information."""
    def __init__(self, status: str, ibkr_connected: bool, data_source: str, last_sync: str):
        self.status = status
        self.ibkr_connected = ibkr_connected
        self.data_source = data_source
        self.last_sync = last_sync


class PortfolioProvider(Protocol):
    """Read-only portfolio data provider."""
    def get_snapshot(self) -> Snapshot:
        """Return current portfolio snapshot."""
        ...

    def get_status(self) -> StatusModel:
        """Return provider status."""
        ...


class MockPortfolioProvider:
    """Mock provider loading fixed fixture."""
    def __init__(self) -> None:
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "mock_portfolio.json"
        with open(fixture_path) as f:
            import json
            data = json.load(f)
        self._snapshot = Snapshot.model_validate(data)

    def get_snapshot(self) -> Snapshot:
        return Snapshot.model_validate(self._snapshot.model_dump())

    def get_status(self) -> StatusModel:
        return StatusModel(
            status="ok",
            ibkr_connected=False,
            data_source="mock",
            last_sync=self._snapshot.as_of.isoformat()
        )


class IBKRPortfolioProvider:
    """IBKR provider skeleton for future implementation."""
    # Future: connectAsync(readonly=True), private _client

    def get_snapshot(self) -> Snapshot:
        raise NotImplementedError("IBKR provider not yet implemented")

    def get_status(self) -> StatusModel:
        raise NotImplementedError("IBKR provider not yet implemented")
