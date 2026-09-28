import { useEffect, useState } from 'react';
import { RefreshCw, Layers, ChevronDown, ChevronRight, Search } from 'lucide-react';
import { fetchPortfolioData, type PortfolioData } from './api';
import type { Position, Underlying } from './types';

type Tab = 'strategies' | 'underlyings' | 'raw';

const formatCurrency = (value: number | null, currency = 'USD'): string => {
  if (value === null) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
};

const formatNumber = (value: number | null): string => {
  if (value === null) return '—';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
};

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return '—';
  // Parse as UTC to prevent date shift
  const date = new Date(dateStr + 'T00:00:00Z');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
};

const formatTimestamp = (isoStr: string | null): string => {
  if (!isoStr) return '—';
  // Explicitly format as UTC
  const date = new Date(isoStr);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short'
  });
};

const strategyOrder = ['UNH', 'DRAM', 'SPMO', 'NVDA'];

export default function App() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [previousData, setPreviousData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('strategies');
  const [search, setSearch] = useState('');
  const [expandedStrategies, setExpandedStrategies] = useState<Set<string>>(new Set());
  const [expandedRawPositions, setExpandedRawPositions] = useState<Set<string>>(new Set());

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPortfolioData();
      setData(result);
      setPreviousData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
      // Keep previous data if available
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const toggleStrategy = (id: string) => {
    setExpandedStrategies((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleRawPosition = (id: string) => {
    setExpandedRawPositions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = (expand: boolean) => {
    if (expand && data) {
      setExpandedStrategies(new Set(data.strategies.map((s) => s.id)));
    } else {
      setExpandedStrategies(new Set());
    }
  };

  const displayData = data || previousData;

  const filteredUnderlyings = displayData?.underlyings.filter((u) =>
    u.symbol.toLowerCase().includes(search.toLowerCase())
  );

  const sortedUnderlyings = filteredUnderlyings
    ? [...filteredUnderlyings].sort((a, b) => {
        const aIndex = strategyOrder.indexOf(a.symbol);
        const bIndex = strategyOrder.indexOf(b.symbol);
        if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
        if (aIndex !== -1) return -1;
        if (bIndex !== -1) return 1;
        return a.symbol.localeCompare(b.symbol);
      })
    : [];

  const filteredPositions = displayData?.positions.filter((p) =>
    p.symbol.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="header-left">
            <div className="brand-mark">
              <Layers size={20} />
            </div>
            <div className="header-title">
              <h1>ComboLens</h1>
              <p className="header-tagline">IBKR gives me legs. ComboLens tells me what I actually own.</p>
              <p className="header-subline">See each strategy. Track what it earns.</p>
              <div className="header-badges">
                <span className="badge badge-gray">Work in progress</span>
                <span className="badge badge-gray">Draft</span>
                <span className="badge badge-gray">Read only</span>
              </div>
            </div>
          </div>
          {displayData && (
            <div className="header-status">
              <span className={displayData.status.ibkr_connected ? 'status-online' : 'status-offline'}>
                {displayData.status.ibkr_connected ? 'Gateway Online' : 'Gateway Offline'}
              </span>
              <span className="status-mock">Showing {displayData.status.data_source} data</span>
            </div>
          )}
        </div>
      </header>

      <main className="main">
        {loading && (
          <div className="loading">
            <RefreshCw className="spin" size={32} />
            <p>Loading portfolio...</p>
          </div>
        )}

        {error && (
          <div className="error" role="alert">
            <p>{error}</p>
            {previousData && <p className="error-previous">Showing previous snapshot</p>}
            <button onClick={loadData}>Retry</button>
          </div>
        )}

        {displayData && !loading && (
          <>
            <section className="metrics">
              <div className="metrics-snapshot">
                Snapshot · {displayData.status.last_sync ? formatTimestamp(displayData.status.last_sync) : 'No sync time'}
              </div>
              <div className="metrics-grid">
                <div className="metric-primary">
                  <div className="metric-label">Portfolio Value</div>
                  <div className="metric-value">{formatCurrency(displayData.account.net_liquidation, displayData.account.currency)}</div>
                </div>
                <div className="metric-primary">
                  <div className="metric-label">Daily P&L</div>
                  <div className={`metric-value ${(displayData.account.daily_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {formatCurrency(displayData.account.daily_pnl, displayData.account.currency)}
                  </div>
                </div>
              </div>
              <div className="metrics-secondary">
                <div className="metric-item">
                  <span className="metric-label">Cash</span>
                  <span className="metric-value">{formatCurrency(displayData.account.cash, displayData.account.currency)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Net unrealized P&L</span>
                  <span className={`metric-value ${(displayData.account.unrealized_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {formatCurrency(displayData.account.unrealized_pnl, displayData.account.currency)}
                  </span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Maintenance Margin</span>
                  <span className="metric-value">{formatCurrency(displayData.account.maintenance_margin, displayData.account.currency)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Excess Liquidity</span>
                  <span className="metric-value">{formatCurrency(displayData.account.excess_liquidity, displayData.account.currency)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">Buying Power</span>
                  <span className="metric-value">{formatCurrency(displayData.account.buying_power, displayData.account.currency)}</span>
                </div>
              </div>
              {displayData.account.cash !== null && displayData.account.net_liquidation !== null && displayData.account.net_liquidation > 0 && (
                <>
                <div className="composition-bar">
                  <div
                    className="composition-cash"
                    style={{
                      width: `${Math.max(0, Math.min(100, (displayData.account.cash / displayData.account.net_liquidation) * 100))}%`,
                    }}
                    title={`Cash: ${formatCurrency(displayData.account.cash, displayData.account.currency)} (${((displayData.account.cash / displayData.account.net_liquidation) * 100).toFixed(1)}%)`}
                  />
                  <div
                    className="composition-holdings"
                    title={`Holdings: ${formatCurrency(displayData.account.net_liquidation - displayData.account.cash, displayData.account.currency)} (${(((displayData.account.net_liquidation - displayData.account.cash) / displayData.account.net_liquidation) * 100).toFixed(1)}%)`}
                  />
                </div>
                <div className="composition-labels">
                  <span>Cash {((displayData.account.cash / displayData.account.net_liquidation) * 100).toFixed(1)}%</span>
                  <span>Holdings {(((displayData.account.net_liquidation - displayData.account.cash) / displayData.account.net_liquidation) * 100).toFixed(1)}%</span>
                </div>
                </>
              )}
            </section>

            <section className="toolbar">
              <h2>Portfolio</h2>
              <div className="toolbar-controls">
                <div className="tabs" role="tablist">
                  <button
                    role="tab"
                    aria-selected={tab === 'strategies'}
                    onClick={() => setTab('strategies')}
                    className={tab === 'strategies' ? 'active' : ''}
                  >
                    Strategies
                  </button>
                  <button
                    role="tab"
                    aria-selected={tab === 'underlyings'}
                    onClick={() => setTab('underlyings')}
                    className={tab === 'underlyings' ? 'active' : ''}
                  >
                    Underlyings
                  </button>
                  <button
                    role="tab"
                    aria-selected={tab === 'raw'}
                    onClick={() => setTab('raw')}
                    className={tab === 'raw' ? 'active' : ''}
                  >
                    Raw Positions
                  </button>
                </div>
                <div className="toolbar-actions">
                  <div className="search-box">
                    <Search size={16} />
                    <input
                      type="text"
                      placeholder="Search symbols"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      aria-label="Search symbols"
                    />
                  </div>
                  <button onClick={loadData} className="btn-icon" aria-label="Refresh" disabled={loading}>
                    <RefreshCw size={16} />
                    Refresh
                  </button>
                  {tab === 'strategies' && (
                    <>
                      <button onClick={() => toggleAll(true)} className="btn-icon">
                        Expand all
                      </button>
                      <button onClick={() => toggleAll(false)} className="btn-icon">
                        Collapse all
                      </button>
                    </>
                  )}
                </div>
              </div>
            </section>

            <section className="content">
              {tab === 'strategies' && (
                <StrategiesView
                  underlyings={sortedUnderlyings}
                  positions={displayData.positions}
                  expandedStrategies={expandedStrategies}
                  onToggle={toggleStrategy}
                />
              )}
              {tab === 'underlyings' && <UnderlyingsView underlyings={sortedUnderlyings} />}
              {tab === 'raw' && (
                <RawPositionsView
                  positions={filteredPositions || []}
                  expandedPositions={expandedRawPositions}
                  onToggle={toggleRawPosition}
                />
              )}
            </section>
          </>
        )}
      </main>

      <footer className="footer">
        <p>
          This interface displays portfolio data for informational purposes only. Strategy classifications
          are algorithmic interpretations and should not be considered investment advice.
        </p>
      </footer>
    </div>
  );
}

function StrategiesView({
  underlyings,
  positions,
  expandedStrategies,
  onToggle,
}: {
  underlyings: Underlying[];
  positions: Position[];
  expandedStrategies: Set<string>;
  onToggle: (id: string) => void;
}) {
  const positionsById = new Map(positions.map((p) => [p.id, p]));

  if (underlyings.length === 0) {
    return (
      <div className="empty-state">
        <p>No matching symbols found</p>
      </div>
    );
  }

  return (
    <div className="strategies">
      {underlyings.map((underlying) => {
        const strategies = underlying.strategies;
        const key = `${underlying.account_id}-${underlying.currency}-${underlying.symbol}`;

        return (
          <div key={key} className="underlying-group">
            <div className="underlying-header">
              <h3>{underlying.symbol}</h3>
              {underlying.underlying_price !== null && (
                <span className="underlying-price">{formatCurrency(underlying.underlying_price, underlying.currency)}</span>
              )}
            </div>

            {strategies.map((strategy) => {
              const isExpanded = expandedStrategies.has(strategy.id);
              const isUnmatched = strategy.strategy_type === 'UNMATCHED';
              const isMultiLeg = strategy.legs.length > 1;

              // Grouping describes structural matching, not original trade intent.
              const showAutoGrouped = !isUnmatched && isMultiLeg;

              return (
                <div key={strategy.id} className="card strategy-card" data-testid="strategy-card">
                  <div className="card-header">
                    <div className="card-title">
                      <button
                        className="expand-btn"
                        onClick={() => onToggle(strategy.id)}
                        aria-expanded={isExpanded}
                        aria-label={isExpanded ? 'Collapse legs' : 'Expand legs'}
                      >
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                      <span className="strategy-name">{strategy.name}{strategy.name.includes("×") ? "" : ` ×${strategy.quantity}`}</span>
                      {isUnmatched && (
                        <span className="badge badge-amber" title={strategy.explanation}>UNMATCHED</span>
                      )}
                      {showAutoGrouped && (
                        <span className="badge badge-teal">Auto-grouped</span>
                      )}
                      {strategy.performance?.source === 'mock_history' && (
                        <span className="badge badge-gray">Mock history</span>
                      )}
                    </div>
                    <div className="card-metrics">
                      <div className="card-metric">
                        <span className="label">Market value</span>
                        <span className="value">{formatCurrency(strategy.market_value, strategy.currency)}</span>
                      </div>
                      <div className="card-metric">
                        <span className="label">Unrealized P&L</span>
                        <span className={`value ${(strategy.unrealized_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                          {formatCurrency(strategy.unrealized_pnl, strategy.currency)}
                        </span>
                      </div>
                      {strategy.performance && (
                        <div className="card-metric">
                          <span className="label">Since opening (net)</span>
                          <span className={`value ${strategy.performance.source === 'unavailable' ? '' : (strategy.performance.total_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                            {strategy.performance.source === 'unavailable' || strategy.performance.total_pnl === null
                              ? '—'
                              : formatCurrency(strategy.performance.total_pnl, strategy.currency)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="card-summary">
                    {isUnmatched && (
                      <div className="explanation">
                        <strong>Reason:</strong> {strategy.explanation}
                      </div>
                    )}
                    {strategy.legs.length > 0 && (
                      <div className="legs-summary">
                        {strategy.legs.map((leg) => {
                          const pos = positionsById.get(leg.position_id);
                          if (!pos) return null;

                          if (pos.security_type === 'OPTION') {
                            return (
                              <span key={leg.position_id} className="leg-summary-item">
                                {pos.option_type ?? 'Option'} ${pos.strike ?? '—'} {formatDate(pos.expiration)}
                              </span>
                            );
                          }
                          return null;
                        }).filter(Boolean)}
                      </div>
                    )}
                  </div>

                  {isExpanded && (
                    <div className="card-body">
                      {strategy.performance && (
                        <div className="performance-panel">
                          {strategy.performance.source === 'unavailable' ? (
                            <div className="performance-unavailable">
                              <span className="performance-label">Opening history unavailable</span>
                              {strategy.performance.reason && (
                                <span className="performance-reason">({strategy.performance.reason})</span>
                              )}
                            </div>
                          ) : (
                            <div className="performance-breakdown">
                              <div className="performance-item">
                                <span className="performance-label">Opened</span>
                                <span className="performance-value">{formatTimestamp(strategy.performance.opened_at)}</span>
                              </div>
                              <div className="performance-item">
                                <span className="performance-label">Realized P&L</span>
                                <span className={`performance-value ${(strategy.performance.realized_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                                  {strategy.performance.realized_pnl !== null ? formatCurrency(strategy.performance.realized_pnl, strategy.currency) : '—'}
                                </span>
                              </div>
                              <div className="performance-item">
                                <span className="performance-label">Fees</span>
                                <span className="performance-value">
                                  {strategy.performance.fees !== null ? formatCurrency(strategy.performance.fees, strategy.currency) : '—'}
                                </span>
                              </div>
                              <div className="performance-item">
                                <span className="performance-label">Net since opening</span>
                                <span className={`performance-value ${(strategy.performance.total_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                                  {strategy.performance.total_pnl !== null ? formatCurrency(strategy.performance.total_pnl, strategy.currency) : '—'}
                                </span>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      <div className="legs">
                        {strategy.legs.map((leg) => {
                          const pos = positionsById.get(leg.position_id);
                          if (!pos) return null;

                          const direction = leg.allocated_quantity > 0 ? 'LONG' : 'SHORT';
                          const signedQty = leg.allocated_quantity > 0 ? `+${leg.allocated_quantity}` : `${leg.allocated_quantity}`;

                          return (
                            <div key={leg.position_id} className="leg">
                              <div className="leg-header">
                                <span className={`direction direction-${direction.toLowerCase()}`}>
                                  {direction}
                                </span>
                                <span className="leg-description">
                                  {pos.security_type === 'OPTION' ? (
                                    <>
                                      {signedQty} × {pos.option_type ?? 'Option'} ${pos.strike ?? '—'} {formatDate(pos.expiration)}
                                    </>
                                  ) : (
                                    <>
                                      {signedQty} shares {pos.symbol}
                                    </>
                                  )}
                                </span>
                              </div>
                              <div className="leg-details">
                                <span>Value: {formatCurrency(leg.allocated_value, pos.currency)}</span>
                                <span>Unrealized P&L: {formatCurrency(leg.allocated_pnl, pos.currency)}</span>
                                <span>Account: {pos.account_id}</span>
                                <span>Currency: {pos.currency}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function UnderlyingsView({ underlyings }: { underlyings: Underlying[] }) {
  if (underlyings.length === 0) {
    return (
      <div className="empty-state">
        <p>No matching symbols found</p>
      </div>
    );
  }

  return (
    <div className="underlyings">
      {underlyings.map((underlying) => {
        const key = `${underlying.account_id}-${underlying.currency}-${underlying.symbol}`;

        return (
          <div key={key} className="card">
            <div className="card-header">
              <div className="card-title">
                <h3>{underlying.symbol}</h3>
                {underlying.underlying_price !== null && (
                  <span className="underlying-price">{formatCurrency(underlying.underlying_price, underlying.currency)}</span>
                )}
              </div>
              <div className="card-metrics">
                <div className="card-metric">
                  <span className="label">Net Value</span>
                  <span className="value">{formatCurrency(underlying.net_value, underlying.currency)}</span>
                </div>
                <div className="card-metric">
                  <span className="label">Net unrealized P&L</span>
                  <span className={`value ${(underlying.net_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {formatCurrency(underlying.net_pnl, underlying.currency)}
                  </span>
                </div>
              </div>
            </div>
            <div className="card-body">
              <div className="underlying-summary">
                <div className="summary-item">
                  <span className="label">Total Positions</span>
                  <span className="value">{underlying.positions.length}</span>
                </div>
                <div className="summary-item">
                  <span className="label">Shares</span>
                  <span className="value">
                    {formatNumber(
                      underlying.positions
                        .filter((p) => p.security_type === 'STOCK')
                        .reduce((sum, p) => sum + p.quantity, 0)
                    )}
                  </span>
                </div>
                <div className="summary-item">
                  <span className="label">Strategies</span>
                  <span className="value">{underlying.strategies.length}</span>
                </div>
              </div>
              {underlying.strategies.length > 0 && (
                <div className="strategy-list">
                  <h4>Contained Strategies</h4>
                  {underlying.strategies.map((s) => (
                    <div key={s.id} className="strategy-item">
                      {s.name}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RawPositionsView({
  positions,
  expandedPositions,
  onToggle,
}: {
  positions: Position[];
  expandedPositions: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (positions.length === 0) {
    return (
      <div className="empty-state">
        <p>No matching symbols found</p>
      </div>
    );
  }

  return (
    <div className="raw-positions">
      {positions.map((pos) => {
        const isExpanded = expandedPositions.has(pos.id);
        const signedQty = pos.quantity >= 0 ? `+${pos.quantity}` : `${pos.quantity}`;

        return (
          <div key={pos.id} className="card">
            <div className="card-header">
              <div className="card-title">
                <button
                  className="expand-btn"
                  onClick={() => onToggle(pos.id)}
                  aria-expanded={isExpanded}
                  aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
                >
                  {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </button>
                <h3>{pos.symbol}</h3>
                <span className="badge badge-gray">{pos.security_type}</span>
              </div>
              <div className="card-metrics">
                <div className="card-metric">
                  <span className="label">Quantity</span>
                  <span className="value">{signedQty}</span>
                </div>
                <div className="card-metric">
                  <span className="label">Value</span>
                  <span className="value">{formatCurrency(pos.market_value, pos.currency)}</span>
                </div>
                <div className="card-metric">
                  <span className="label">Unrealized P&L</span>
                  <span className={`value ${(pos.unrealized_pnl || 0) >= 0 ? 'metric-positive' : 'metric-negative'}`}>
                    {formatCurrency(pos.unrealized_pnl, pos.currency)}
                  </span>
                </div>
              </div>
            </div>

            <div className="card-summary">
              <div className="raw-compact">
                {pos.security_type === 'OPTION' && (
                  <>
                    <span><strong>Type:</strong> {pos.option_type}</span>
                    <span><strong>Strike:</strong> ${pos.strike}</span>
                    <span><strong>Expiry:</strong> {formatDate(pos.expiration)}</span>
                  </>
                )}
                <span><strong>Account:</strong> {pos.account_id}</span>
                <span><strong>Currency:</strong> {pos.currency}</span>
                {pos.market_price !== null && (
                  <span><strong>Price:</strong> ${formatNumber(pos.market_price)}</span>
                )}
              </div>
            </div>

            <details className="card-body" open={isExpanded} onToggle={(event) => {
              if (event.currentTarget.open !== isExpanded) onToggle(pos.id);
            }}>
              <summary>Normalized record</summary>
              <pre className="json-display">{JSON.stringify(pos, null, 2)}</pre>
            </details>
          </div>
        );
      })}
    </div>
  );
}
