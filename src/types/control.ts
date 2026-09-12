export type BotStatus = 'RUNNING' | 'STOPPED';
export type ExecutionMode = 'ANALYZE' | 'PAPER' | 'LIVE';
export const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1H', '4H'] as const;
export type Timeframe = typeof TIMEFRAMES[number];
export type ConditionId = 'marketStructure' | 'liquiditySweep' | 'manipulation'
  | 'bodyCloseReclaim' | 'premiumDiscount' | 'range';
export type DecisionOutcome = 'NO_SETUP' | 'WAIT' | 'TRADE_CANDIDATE' | 'BLOCKED' | 'EXECUTED';
export interface StrategyProfile {
  schemaVersion: 'strategy-profile-local-v1';
  preset: 'SWEEP_REVERSAL' | 'CUSTOM';
  timeframes: { context: Timeframe; structure: Timeframe; setup: Timeframe; confirmation: Timeframe };
  conditions: Record<ConditionId, boolean>;
  risk: { riskPerTradePct: string; maxDailyLossPct: string; maxOpenPositions: number };
  trailingStop: 'SWING_BASED' | 'ATR_BASED' | 'OFF';
  executionMode: ExecutionMode;
}
export interface AgentEvent {
  id: string;
  at: string;
  title: string;
  detail: string;
  tone: 'neutral' | 'positive' | 'warning';
  origin: 'LOCAL' | 'BACKEND';
}
export interface MarketSummary {
  symbol: 'BTC-USDT';
  lastPrice: string | null;
  observedAt: string | null;
  source: 'OKX ATK MCP';
  connection: 'DISCONNECTED' | 'CONNECTED';
  dataOrigin: 'MOCK' | 'BACKEND';
  decision: DecisionOutcome | null;
  decisionReason: string;
}
export interface DashboardSnapshot {
  bot: { status: BotStatus; mode: ExecutionMode; startedAt: string | null };
  strategy: StrategyProfile;
  market: MarketSummary;
  autoEarn: 'ON' | 'OFF' | 'UNKNOWN';
  events: AgentEvent[];
}
export const CONDITIONS: ReadonlyArray<{ id: ConditionId; label: string;
  description: string; configurable: boolean; availability: string }> = [
  { id: 'marketStructure', label: 'Market Structure', description: 'Structure context',
    configurable: true, availability: 'Demo config' },
  { id: 'liquiditySweep', label: 'Liquidity Sweep', description: 'Sweep confirmation',
    configurable: true, availability: 'Demo config' },
  { id: 'manipulation', label: 'Manipulation', description: 'Module unavailable',
    configurable: false, availability: 'COMING SOON' },
  { id: 'bodyCloseReclaim', label: 'Body Close Reclaim', description: 'Closed-candle reclaim',
    configurable: true, availability: 'Demo config' },
  { id: 'premiumDiscount', label: 'Premium/Discount', description: 'Context filter',
    configurable: false, availability: 'NOT IMPLEMENTED' },
  { id: 'range', label: 'Range', description: 'Module unavailable',
    configurable: false, availability: 'COMING SOON' },
];
export function createDefaultStrategy(): StrategyProfile {
  return {
    schemaVersion: 'strategy-profile-local-v1', preset: 'SWEEP_REVERSAL',
    timeframes: { context: '4H', structure: '1H', setup: '15m', confirmation: '5m' },
    conditions: { marketStructure: true, liquiditySweep: true, manipulation: false,
      bodyCloseReclaim: true, premiumDiscount: false, range: false },
    risk: { riskPerTradePct: '0.5', maxDailyLossPct: '2', maxOpenPositions: 1 },
    trailingStop: 'OFF', executionMode: 'ANALYZE',
  };
}
export function strategyName(profile: StrategyProfile): string {
  return profile.preset === 'SWEEP_REVERSAL' ? 'Sweep Reversal' : 'Custom';
}
