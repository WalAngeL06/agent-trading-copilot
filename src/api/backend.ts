import type { TradingControlApi } from './control.ts';
import type { DashboardSnapshot, StrategyProfile, MarketSummary, DecisionOutcome } from '../types/control.ts';
import { createDefaultStrategy } from '../types/control.ts';

const viteEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;
const DEFAULT_API_BASE = viteEnv?.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

interface BotStatusWire {
  bot_status: 'running' | 'stopped';
  strategy_state: string;
  execution_mode: 'PAPER';
  market_source: 'OKX_ATK_MCP';
  market_connected: boolean;
  account_auth: 'CONNECTED' | 'AUTH_MISSING' | 'ERROR' | 'UNKNOWN';
  auto_earn_status: 'ON' | 'OFF' | 'UNKNOWN';
}

interface MarketWire {
  last_price?: string;
  observed_at?: string;
}

function decision(value: string): DecisionOutcome | null {
  return ['NO_TRADE', 'NO_SETUP', 'WAIT', 'TRADE_CANDIDATE', 'BLOCKED', 'EXECUTED'].includes(value)
    ? value as DecisionOutcome : null;
}

export class BackendApi implements TradingControlApi {
  readonly kind = 'BACKEND';
  readonly strategyStorage = 'BROWSER';
  private storage: any;
  private apiBase: string;
  private request: typeof fetch;

  constructor(storage?: any, apiBase = DEFAULT_API_BASE, request?: typeof fetch) {
    this.storage = storage;
    this.apiBase = apiBase;
    // Native fetch must keep its global receiver; calling it as this.request would throw.
    this.request = request ?? ((input, init) => fetch(input, init));
  }

  private async fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await this.request(`${this.apiBase}${url}`, options);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    return await response.json() as T;
  }

  async getDashboard(): Promise<DashboardSnapshot> {
    const [statusData, marketData, activityData] = await Promise.all([
      this.fetchJson<BotStatusWire>('/api/v1/bot/status'),
      this.fetchJson<MarketWire>('/api/v1/bot/market'),
      this.fetchJson<{ events?: any[] }>('/api/v1/bot/activity')
        .catch((): { events?: any[] } => ({})),
    ]);
    const strategy = await this.getStrategy();
    const marketSummary: MarketSummary = {
      symbol: 'BTC-USDT',
      lastPrice: marketData.last_price ?? null,
      observedAt: marketData.observed_at ?? null,
      source: 'OKX ATK MCP',
      connection: statusData.market_connected ? 'CONNECTED' : 'DISCONNECTED',
      dataOrigin: 'BACKEND',
      decision: decision(statusData.strategy_state),
      decisionReason: statusData.strategy_state || 'Unknown',
    };
    const events = (activityData.events || []).map((event: any) => ({
      id: event.id, at: event.at, title: event.title, detail: event.detail,
      tone: event.tone || 'neutral', origin: 'BACKEND' as const,
    }));
    return {
      bot: {
        status: statusData.bot_status === 'running' ? 'RUNNING' : 'STOPPED',
        mode: statusData.execution_mode,
        startedAt: null,
      },
      strategy,
      market: marketSummary,
      accountAuth: statusData.account_auth,
      autoEarn: statusData.auto_earn_status,
      events,
    };
  }

  async getStrategy(): Promise<StrategyProfile> {
    if (this.storage) {
      const stored = this.storage.getItem('agent_trading_strategy');
      if (stored) {
        try { return JSON.parse(stored) as StrategyProfile; }
        catch { /* return default */ }
      }
    }
    return createDefaultStrategy();
  }

  async saveStrategy(profile: StrategyProfile): Promise<StrategyProfile> {
    if (this.storage) this.storage.setItem('agent_trading_strategy', JSON.stringify(profile));
    return profile;
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
