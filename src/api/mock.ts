import type { TradingControlApi } from './control.ts';
import type { AgentEvent, DashboardSnapshot, StrategyProfile } from '../types/control.ts';
import { createDefaultStrategy } from '../types/control.ts';
import { assertValidStrategy } from './validation.ts';
export interface ProfileStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
const STORAGE_KEY = 'agent-trading:strategy:local-v1';
const clone = <T>(value: T): T => structuredClone(value);
export function createMockApi(storage?: ProfileStorage): TradingControlApi {
  let profile = createDefaultStrategy();
  let startedAt: string | null = null;
  let sequence = 0;
  const events: AgentEvent[] = [];
  function event(title: string, detail: string, tone: AgentEvent['tone'] = 'neutral') {
    events.unshift({ id: String(++sequence), at: new Date().toISOString(), title, detail, tone, origin: 'LOCAL' });
    events.splice(8);
  }
  event('Control center ready', 'Local demo session. No backend connection.');
  if (storage) {
    try {
      const stored = storage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: unknown = JSON.parse(stored);
        assertValidStrategy(parsed);
        profile = clone(parsed as StrategyProfile);
        event('Strategy restored', 'Loaded settings from this browser.');
      }
    } catch {
      event('Saved settings unavailable', 'Using safe demo defaults. Save again to replace local settings.', 'warning');
    }
  }
  function dashboard(): DashboardSnapshot {
    return clone({
      bot: { status: startedAt ? 'RUNNING' : 'STOPPED', mode: profile.executionMode, startedAt },
      strategy: profile,
      market: { symbol: 'BTC-USDT', lastPrice: null, observedAt: null,
        source: 'OKX ATK MCP', connection: 'DISCONNECTED', dataOrigin: 'MOCK',
        decision: 'NO_SETUP', decisionReason: 'Sample outcome for the UI preview. Strategy engine is not connected.' },
      accountAuth: 'UNKNOWN', autoEarn: 'UNKNOWN', events,
    });
  }
  return {
    kind: 'MOCK',
    strategyStorage: storage ? 'BROWSER' : 'SESSION',
    async getDashboard() { return dashboard(); },
    async getStrategy() { return clone(profile); },
    async saveStrategy(next) {
      if (startedAt) throw new Error('Stop the local bot before saving a strategy.');
      assertValidStrategy(next);
      const candidate = clone(next);
      if (storage) {
        try { storage.setItem(STORAGE_KEY, JSON.stringify(candidate)); }
        catch { throw new Error('Browser storage is unavailable. Strategy was not saved.'); }
      }
      profile = candidate;
      event('Strategy saved', storage ? 'Saved locally in this browser.' : 'Saved for this session only.');
      return clone(profile);
    },
    async startBot() {
      if (profile.executionMode === 'LIVE')
        throw new Error('LIVE execution is unavailable. Choose ANALYZE or PAPER for the local demo.');
      if (!startedAt) {
        startedAt = new Date().toISOString();
        event('Local bot started', profile.executionMode === 'PAPER'
          ? 'PAPER preview only. No simulator, fills or orders.' : 'ANALYZE preview only. No market evaluation.', 'positive');
      }
      return dashboard();
    },
    async stopBot() {
      if (startedAt) {
        startedAt = null;
        event('Local bot stopped', 'Demo controls are idle.');
      }
      return dashboard();
    },
  };
}
