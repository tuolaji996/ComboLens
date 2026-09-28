import type { StatusResponse, AccountMetrics, Position, Strategy, Underlying } from './types';

const TIMEOUT_MS = 10000;

async function fetchWithTimeout(url: string, timeout: number): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

export interface PortfolioData {
  status: StatusResponse;
  account: AccountMetrics;
  positions: Position[];
  strategies: Strategy[];
  underlyings: Underlying[];
}

export async function fetchPortfolioData(): Promise<PortfolioData> {
  const [statusRes, accountRes, positionsRes, strategiesRes, underlyingsRes] = await Promise.all([
    fetchWithTimeout('/api/v1/status', TIMEOUT_MS),
    fetchWithTimeout('/api/v1/account', TIMEOUT_MS),
    fetchWithTimeout('/api/v1/positions', TIMEOUT_MS),
    fetchWithTimeout('/api/v1/strategies', TIMEOUT_MS),
    fetchWithTimeout('/api/v1/underlyings', TIMEOUT_MS),
  ]);

  if (!statusRes.ok || !accountRes.ok || !positionsRes.ok || !strategiesRes.ok || !underlyingsRes.ok) {
    throw new Error('Failed to fetch portfolio data');
  }

  const [status, account, positions, strategies, underlyings] = await Promise.all([
    statusRes.json(),
    accountRes.json(),
    positionsRes.json(),
    strategiesRes.json(),
    underlyingsRes.json(),
  ]);

  return { status, account, positions, strategies, underlyings };
}
