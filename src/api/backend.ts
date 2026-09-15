import type { TradingControlApi, ProfileStorage } from './control.ts';
import type {
  AccountStatus,
  AgentEvent,
  BacktestResult,
  DashboardSnapshot,
  LatestTradeSummary,
  MarketSummary,
  StrategyProfile,
  StrategyState,
} from '../types/control.ts';
import { STRATEGY_STATES } from '../types/control.ts';

const viteEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
const DEFAULT_API_BASE = viteEnv?.VITE_BACKEND_URL || 'http://localhost:8000';

interface BotStatusWire {
  bot_status?: unknown;
  strategy_state?: unknown;
  execution_mode?: unknown;
  market_source?: unknown;
  market_connected?: unknown;
  market_status?: unknown;
  symbol?: unknown;
  last_market_update?: unknown;
  last_private_update?: unknown;
  balance?: unknown;
  account_auth?: unknown;
  auto_earn_status?: unknown;
}

interface MarketWire {
  last_price?: unknown;
  observed_at?: unknown;
}

const record = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};

const stringOrNull = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value : null;

function strategyState(value: unknown): StrategyState {
  return typeof value === 'string' && (STRATEGY_STATES as readonly string[]).includes(value)
    ? value as StrategyState
    : 'UNAVAILABLE';
}

function accountStatus(value: unknown): AccountStatus {
  return typeof value === 'string' && ['CONNECTED', 'AUTH_MISSING', 'ERROR', 'UNKNOWN'].includes(value)
    ? value as AccountStatus
    : 'UNKNOWN';
}

function latestTrade(value: unknown): LatestTradeSummary | null {
  const activity = record(value);
  if (!Array.isArray(activity.trades) || activity.trades.length === 0) return null;
  const trade = record(activity.trades.at(-1));
  return {
    entry: stringOrNull(trade.entry),
    stopLoss: stringOrNull(trade.stop),
    rangeHigh: stringOrNull(trade.range_high),
    remainingPosition: stringOrNull(trade.remaining_quantity),
    realizedPnl: stringOrNull(trade.pnl),
  };
}

function activityEvents(value: unknown): AgentEvent[] {
  const activity = record(value);
  if (!Array.isArray(activity.events)) return [];
  return activity.events.flatMap((raw, index): AgentEvent[] => {
    const event = record(raw);
    const at = stringOrNull(event.at);
    const title = stringOrNull(event.title);
    const detail = stringOrNull(event.detail);
    if (!at || !title || !detail) return [];
    const tone = typeof event.tone === 'string'
      && ['neutral', 'positive', 'warning', 'danger'].includes(event.tone)
      ? event.tone as AgentEvent['tone']
      : 'neutral';
    return [{
      id: stringOrNull(event.id) ?? 'backend-event-' + index,
      at,
      title,
      detail,
      tone,
      origin: 'BACKEND',
    }];
  });
}

export class BackendApi implements TradingControlApi {
  readonly kind = 'BACKEND';
  readonly strategyStorage = 'BACKEND';
  private apiBase: string;
  private request: typeof fetch;

  constructor(_storage?: ProfileStorage, apiBase = DEFAULT_API_BASE, request: typeof fetch = fetch) {
    this.apiBase = apiBase;
    this.request = (...args) => request(...args);
  }

  private async fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await this.request(this.apiBase + url, {
      ...options, signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body?.error?.message || 'Backend request failed (' + response.status + ').');
    }
    return await response.json() as T;
  }

  async getDashboard(): Promise<DashboardSnapshot> {
    const [statusData, marketData, activityData] = await Promise.all([
      this.fetchJson<BotStatusWire>('/api/v1/bot/status'),
      this.fetchJson<MarketWire>('/api/v1/bot/market'),
      this.fetchJson<unknown>('/api/v1/bot/activity'),
    ]);
    if (!['running', 'stopped'].includes(String(statusData.bot_status))
        || statusData.execution_mode !== 'PAPER') {
      throw new Error('Unsupported runtime state. Refresh after checking the backend.');
    }
    const strategy = await this.getStrategy();
    const sourceAvailable = statusData.market_source === 'OKX_ATK_MCP';
    const marketSummary: MarketSummary = {
      symbol: stringOrNull(statusData.symbol) ?? 'UNKNOWN',
      lastPrice: stringOrNull(marketData.last_price),
      observedAt: stringOrNull(marketData.observed_at),
      source: sourceAvailable ? 'OKX_AGENT_TRADE_KIT_MCP' : 'UNAVAILABLE',
      connection: ['CONNECTED', 'WAITING', 'ERROR'].includes(String(statusData.market_status))
        ? statusData.market_status as MarketSummary['connection'] : 'UNKNOWN',
      dataOrigin: 'BACKEND',
    };

    return {
      bot: {
        status: statusData.bot_status === 'running' ? 'RUNNING' : 'STOPPED',
        mode: 'PAPER',
        startedAt: null,
      },
      strategy,
      strategyState: strategyState(statusData.strategy_state),
      market: marketSummary,
      accountAuth: accountStatus(statusData.account_auth),
      autoEarn: 'UNKNOWN',
      lastMarketUpdate: stringOrNull(statusData.last_market_update),
      lastPrivateUpdate: stringOrNull(statusData.last_private_update),
      balance: stringOrNull(statusData.balance),
      latestTrade: latestTrade(activityData),
      events: activityEvents(activityData),
    };
  }

  async getStrategy(): Promise<StrategyProfile> {
    return this.fetchJson<StrategyProfile>('/api/v1/strategy/config');
  }

  async getBacktestResult(): Promise<BacktestResult | null> {
    return null;
  }

  async saveStrategy(profile: StrategyProfile): Promise<StrategyProfile> {
    await this.fetchJson('/api/v1/strategy/config', {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(profile),
    });
    return this.getStrategy();
  }

  async startBot(): Promise<DashboardSnapshot> {
    await this.fetchJson('/api/v1/bot/start', { method: 'POST' });
    return this.getDashboard();
  }

  async stopBot(): Promise<DashboardSnapshot> {
    await this.fetchJson('/api/v1/bot/stop', { method: 'POST' });
    return this.getDashboard();
  }
}
