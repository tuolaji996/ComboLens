"""FastAPI endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.providers import IBKRPortfolioProvider, MockPortfolioProvider, StatusModel
from packages.portfolio_models.models import AccountMetrics, Position, Snapshot


@pytest.fixture
def mock_provider() -> MockPortfolioProvider:
    return MockPortfolioProvider()


@pytest.fixture
def client(mock_provider: MockPortfolioProvider) -> TestClient:
    return TestClient(create_app(mock_provider))


def test_status_endpoint(client: TestClient, mock_provider: MockPortfolioProvider) -> None:
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ibkr_connected"] is False
    assert data["data_source"] == "mock"
    assert data["last_sync"] == mock_provider.get_snapshot().as_of.isoformat()


def test_positions_endpoint_fixture_values(client: TestClient) -> None:
    resp = client.get("/api/v1/positions")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 12
    unh_stock = next(p for p in positions if p["id"] == "pos_unh_stock")
    assert unh_stock["symbol"] == "UNH"
    assert unh_stock["quantity"] == 2.0
    assert unh_stock["market_value"] == 753.94


def test_strategies_endpoint_allocations(client: TestClient) -> None:
    resp = client.get("/api/v1/strategies")
    assert resp.status_code == 200
    strategies = resp.json()

    # Find collar strategy - quantity should be 1 strategy unit
    dram_collar = next((s for s in strategies if s["symbol"] == "DRAM" and s["strategy_type"] == "COLLAR"), None)
    assert dram_collar is not None
    assert len(dram_collar["legs"]) == 3
    assert dram_collar["quantity"] == 1.0

    # Stock leg should have 100 shares
    stock_leg = next((leg for leg in dram_collar["legs"] if leg["position_id"] == "pos_dram_stock"), None)
    assert stock_leg is not None
    assert stock_leg["allocated_quantity"] == 100.0


def test_underlyings_endpoint_sums(client: TestClient) -> None:
    resp = client.get("/api/v1/underlyings")
    assert resp.status_code == 200
    underlyings = resp.json()

    unh = next((u for u in underlyings if u["symbol"] == "UNH"), None)
    assert unh is not None
    assert len(unh["positions"]) == 3
    assert unh["net_value"] == 753.94 + (-2310.0) + 3774.0
    assert unh["net_pnl"] == 15.0 + 25.0 + (-59.7)
    assert unh["underlying_price"] == 376.97


def test_account_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/account")
    assert resp.status_code == 200
    account = resp.json()
    assert account["currency"] == "USD"
    assert account["net_liquidation"] == 115777.94
    assert account["cash"] == 100000.0


def test_deep_copy_isolation(mock_provider: MockPortfolioProvider) -> None:
    snap1 = mock_provider.get_snapshot()
    snap2 = mock_provider.get_snapshot()

    assert snap1 is not snap2
    assert snap1.positions[0] is not snap2.positions[0]

    # Verify mutation doesn't affect source
    positions_before = len(mock_provider.get_snapshot().positions)
    snap_mut = mock_provider.get_snapshot()
    positions_list = list(snap_mut.positions)
    positions_list.append(positions_list[0])  # This should not affect source
    assert len(mock_provider.get_snapshot().positions) == positions_before


def test_consistent_timestamp(mock_provider: MockPortfolioProvider) -> None:
    snap1 = mock_provider.get_snapshot()
    snap2 = mock_provider.get_snapshot()
    status = mock_provider.get_status()

    assert snap1.as_of == snap2.as_of
    assert status.last_sync == snap1.as_of.isoformat()


@pytest.mark.parametrize("method,path", [
    ("post", "/api/v1/positions"),
    ("put", "/api/v1/positions"),
    ("patch", "/api/v1/account"),
    ("delete", "/api/v1/status"),
])
def test_write_methods_rejected(client: TestClient, method: str, path: str) -> None:
    resp = getattr(client, method)(path)
    assert resp.status_code == 405


def test_openapi_spec_safety() -> None:
    """Verify OpenAPI spec contains exactly 5 paths, all GET only."""
    app = create_app(MockPortfolioProvider())
    openapi = app.openapi()
    paths = openapi["paths"]

    # Exactly 5 paths under /api/v1
    api_paths = [p for p in paths.keys() if p.startswith("/api/v1")]
    assert len(api_paths) == 5, f"Expected 5 paths, got {len(api_paths)}: {api_paths}"

    # All paths support only GET
    for path, methods in paths.items():
        if path.startswith("/api/v1"):
            assert list(methods.keys()) == ["get"], f"{path} has methods: {list(methods.keys())}"

    # Runtime: no POST/PUT/PATCH/DELETE routes exist
    route_methods = [(r.path, r.methods) for r in app.routes if hasattr(r, "methods")]
    for path, methods in route_methods:
        if path.startswith("/api/v1"):
            forbidden = methods & {"POST", "PUT", "PATCH", "DELETE"}
            assert not forbidden, f"{path} has forbidden methods: {forbidden}"


def test_ibkr_provider_fails() -> None:
    provider = IBKRPortfolioProvider()

    with pytest.raises(NotImplementedError):
        provider.get_snapshot()

    with pytest.raises(NotImplementedError):
        provider.get_status()


def test_invalid_provider_config() -> None:
    import os
    original = os.environ.get("PORTFOLIO_PROVIDER")
    try:
        os.environ["PORTFOLIO_PROVIDER"] = "invalid"
        with pytest.raises(ValueError, match="Invalid PORTFOLIO_PROVIDER"):
            create_app()
    finally:
        if original:
            os.environ["PORTFOLIO_PROVIDER"] = original
        else:
            os.environ.pop("PORTFOLIO_PROVIDER", None)


def test_ibkr_provider_config_raises() -> None:
    """PORTFOLIO_PROVIDER=ibkr should raise NotImplementedError at create_app."""
    import os
    original = os.environ.get("PORTFOLIO_PROVIDER")
    try:
        os.environ["PORTFOLIO_PROVIDER"] = "ibkr"
        with pytest.raises(NotImplementedError, match="IBKR provider not yet implemented"):
            create_app()
    finally:
        if original:
            os.environ["PORTFOLIO_PROVIDER"] = original
        else:
            os.environ.pop("PORTFOLIO_PROVIDER", None)


def test_underlyings_no_double_count(client: TestClient) -> None:
    """Ensure positions aren't double-counted in underlyings."""
    resp = client.get("/api/v1/underlyings")
    underlyings = resp.json()

    all_position_ids = set()
    for u in underlyings:
        for p in u["positions"]:
            assert p["id"] not in all_position_ids, f"Position {p['id']} appears multiple times"
            all_position_ids.add(p["id"])


def test_underlyings_partial_null_values() -> None:
    """Aggregates should return None if ANY position has None market_value or unrealized_pnl."""
    from datetime import datetime

    class PartialNullProvider:
        def get_snapshot(self) -> Snapshot:
            return Snapshot(
                as_of=datetime(2024, 1, 15, 16, 0, 0),
                account=AccountMetrics(
                    currency="USD",
                    net_liquidation=100000.0,
                    cash=50000.0,
                    excess_liquidity=60000.0,
                ),
                positions=[
                    Position(
                        id="pos1",
                        account_id="U12345",
                        symbol="AAPL",
                        currency="USD",
                        security_type="STOCK",
                        multiplier=1,
                        quantity=100.0,
                        market_value=16000.0,
                        unrealized_pnl=1000.0,
                        underlying_price=160.0,
                    ),
                    Position(
                        id="pos2",
                        account_id="U12345",
                        symbol="AAPL",
                        currency="USD",
                        security_type="OPTION",
                        multiplier=100,
                        quantity=1.0,
                        market_value=None,  # Missing value
                        unrealized_pnl=50.0,
                        underlying_price=160.0,
                    ),
                    Position(
                        id="pos3",
                        account_id="U12345",
                        symbol="MSFT",
                        currency="USD",
                        security_type="STOCK",
                        multiplier=1,
                        quantity=50.0,
                        market_value=16000.0,
                        unrealized_pnl=None,  # Missing value
                        underlying_price=320.0,
                    ),
                ],
            )

        def get_status(self) -> StatusModel:
            return StatusModel(
                status="ok",
                ibkr_connected=False,
                data_source="test",
                last_sync="2024-01-15T16:00:00"
            )

    client = TestClient(create_app(PartialNullProvider()))
    resp = client.get("/api/v1/underlyings")
    assert resp.status_code == 200
    underlyings = resp.json()

    aapl = next(u for u in underlyings if u["symbol"] == "AAPL")
    assert aapl["net_value"] is None, "Should be None when any position.market_value is None"

    msft = next(u for u in underlyings if u["symbol"] == "MSFT")
    assert msft["net_pnl"] is None, "Should be None when any position.unrealized_pnl is None"
