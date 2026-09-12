import type { DashboardSnapshot, StrategyProfile } from '../types/control.ts';
/** Transport boundary. Components never own network calls or storage. */
export interface TradingControlApi {
  readonly kind: 'MOCK' | 'BACKEND';
  readonly strategyStorage: 'BROWSER' | 'SESSION' | 'BACKEND';
  getDashboard(): Promise<DashboardSnapshot>;
  getStrategy(): Promise<StrategyProfile>;
  saveStrategy(profile: StrategyProfile): Promise<StrategyProfile>;
  startBot(): Promise<DashboardSnapshot>;
  stopBot(): Promise<DashboardSnapshot>;
}
