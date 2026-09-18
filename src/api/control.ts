import type { BacktestResult, DashboardSnapshot, StrategyProfile, LiraPreference } from '../types/control.ts';

export interface ProfileStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** Transport boundary. Components never own network calls or storage. */
export interface TradingControlApi {
  readonly kind: 'MOCK' | 'BACKEND';
  readonly strategyStorage: 'BROWSER' | 'SESSION' | 'BACKEND';
  getDashboard(): Promise<DashboardSnapshot>;
  getStrategy(): Promise<StrategyProfile>;
  getBacktestResult(): Promise<BacktestResult | null>;
  saveStrategy(profile: StrategyProfile): Promise<StrategyProfile>;
  saveLiraPreference(preference: LiraPreference): Promise<DashboardSnapshot>;
  startBot(): Promise<DashboardSnapshot>;
  stopBot(): Promise<DashboardSnapshot>;
}
