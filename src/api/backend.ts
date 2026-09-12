import type { TradingControlApi } from './control.ts';
import type { DashboardSnapshot, StrategyProfile, MarketSummary, DecisionOutcome } from '../types/control.ts';
import { createDefaultStrategy } from '../types/control.ts';

const API_BASE = 'http://127.0.0.1:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, options);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json() as T;
}

export class BackendApi implements TradingControlApi {
  readonly kind = 'BACKEND';
  readonly strategyStorage = 'BROWSER';
  private storage: any;

  constructor(storage?: any) {
    this.storage = storage;
  }

  async getDashboard(): Promise<DashboardSnapshot> {
    const statusPromise = fetchJson<any>('/api/v1/bot/status');
    const marketPromise = fetchJson<any>('/api/v1/bot/market');
    
    const [statusData, marketData] = await Promise.all([statusPromise, marketPromise]);
    
    let lastPrice = null;
    let observedAt = null;
    if (marketData && marketData.prices && marketData.prices.length > 0) {
      lastPrice = String(marketData.prices[0]);
    }
    
    const marketSummary: MarketSummary = {
      symbol: 'BTC-USDT',
      lastPrice,
      observedAt,
      source: 'OKX ATK MCP',
      connection: statusData.bot_status === 'running' ? 'CONNECTED' : 'DISCONNECTED',
      dataOrigin: 'BACKEND',
      decision: statusData.strategy_state as DecisionOutcome,
      decisionReason: statusData.strategy_state || 'Unknown',
    };

    const strategy = await this.getStrategy();

    return {
      bot: { 
        status: statusData.bot_status === 'running' ? 'RUNNING' : 'STOPPED', 
        mode: strategy.executionMode, 
        startedAt: null 
      },
      strategy,
      market: marketSummary,
      autoEarn: 'UNKNOWN',
      events: []
    };
  }

  async getStrategy(): Promise<StrategyProfile> {
    if (this.storage) {
      const stored = this.storage.getItem('agent_trading_strategy');
      if (stored) {
        try {
          return JSON.parse(stored) as StrategyProfile;
        } catch { /* return default */ }
      }
    }
    return createDefaultStrategy();
  }

  async saveStrategy(profile: StrategyProfile): Promise<StrategyProfile> {
    if (this.storage) {
      this.storage.setItem('agent_trading_strategy', JSON.stringify(profile));
    }
    return profile;
  }

  async startBot(): Promise<DashboardSnapshot> {
    await fetchJson('/api/v1/bot/start', { method: 'POST' });
    return this.getDashboard();
  }

  async stopBot(): Promise<DashboardSnapshot> {
    await fetchJson('/api/v1/bot/stop', { method: 'POST' });
    return this.getDashboard();
  }
}
