export interface StatusResponse {
  status: string;
  ibkr_connected: boolean;
  data_source: string;
  last_sync: string;
}

export interface AccountMetrics {
  currency: string;
  net_liquidation: number | null;
  cash: number | null;
  daily_pnl: number | null;
  unrealized_pnl: number | null;
  maintenance_margin: number | null;
  excess_liquidity: number | null;
  buying_power: number | null;
}

export type SecurityType = 'STOCK' | 'OPTION';
export type OptionType = 'CALL' | 'PUT';

export interface Position {
  id: string;
  account_id: string;
  symbol: string;
  currency: string;
  security_type: SecurityType;
  quantity: number;
  option_type: OptionType | null;
  strike: number | null;
  expiration: string | null;
  multiplier: number;
  market_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  underlying_price: number | null;
}

export interface StrategyLeg {
  position_id: string;
  allocated_quantity: number;
  allocated_value: number | null;
  allocated_pnl: number | null;
}

export type StrategyType =
  | 'COLLAR'
  | 'COVERED_CALL'
  | 'PROTECTIVE_PUT'
  | 'CALENDAR_CALL'
  | 'CALENDAR_PUT'
  | 'DIAGONAL'
  | 'VERTICAL_CALL'
  | 'VERTICAL_PUT'
  | 'LONG_CALL'
  | 'LONG_PUT'
  | 'SHORT_CALL'
  | 'SHORT_PUT'
  | 'STOCK'
  | 'UNMATCHED';

export interface StrategyPerformance {
  source: 'mock_history' | 'unavailable';
  opened_at: string | null;
  realized_pnl: number | null;
  fees: number | null;
  total_pnl: number | null;
  reason: string | null;
}

export interface Strategy {
  id: string;
  account_id: string;
  symbol: string;
  currency: string;
  strategy_type: StrategyType;
  quantity: number;
  name: string;
  legs: StrategyLeg[];
  market_value: number | null;
  unrealized_pnl: number | null;
  performance?: StrategyPerformance | null;
  confidence: number;
  explanation: string;
}

export interface Underlying {
  account_id: string;
  symbol: string;
  currency: string;
  positions: Position[];
  strategies: Strategy[];
  net_value: number | null;
  net_pnl: number | null;
  underlying_price: number | null;
}
