export type BotStatus = 'RUNNING' | 'STOPPED';
export type ExecutionMode = 'PAPER';

export const TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H'] as const;
export type Timeframe = typeof TIMEFRAMES[number];

export const ENTRY_LEVELS = ['FVG_LOW', 'FVG_EQ', 'FVG_HIGH'] as const;
export type EntryLevel = typeof ENTRY_LEVELS[number];

export const STRATEGY_STATES = [
  'WAITING_FOR_BIAS',
  'WAITING_FOR_RANGE',
  'WAITING_FOR_MANIPULATION',
  'WAITING_FOR_FVG',
  'PENDING_ENTRY',
  'TRADE_OPEN',
  'IN_POSITION',
  'CLOSED',
  'RUNNER_OPEN',
  'NO_TRADE',
  'NO_SETUP',
  'WAIT',
  'BLOCKED',
  'EXECUTED',
] as const;
export type StrategyState = typeof STRATEGY_STATES[number] | 'UNAVAILABLE';

export interface PartialTakeProfit {
  id: string;
  rMultiple: string;
  closePct: string;
}

export interface StrategyProfile {
  schemaVersion: 'strategy-config-v1';
  profileId: 'STRATEGY_V1';
  timeframes: {
    bias: Timeframe;
    range: Timeframe;
    entry: Timeframe;
  };
  entry: {
    level: EntryLevel;
    secondaryFvgSupport: boolean;
  };
  risk: {
    riskPct: string;
    minimumRR: string;
  };
  management: {
    breakEvenEnabled: boolean;
    breakEvenTriggerR: string;
    trailingEnabled: boolean;
    trailingBuffer: string;
  };
  exits: {
    partialTakeProfits: PartialTakeProfit[];
    runnerPct: string;
  };
  executionMode: 'PAPER';
}

export interface AgentEvent {
  id: string;
  at: string;
  title: string;
  detail: string;
  tone: 'neutral' | 'positive' | 'warning' | 'danger';
  origin: 'LOCAL' | 'BACKEND';
}

export interface MarketSummary {
  symbol: string;
  lastPrice: string | null;
  observedAt: string | null;
  source: 'OKX_AGENT_TRADE_KIT_MCP' | 'UNAVAILABLE';
  connection: 'CONNECTED' | 'WAITING' | 'RECONNECTING' | 'ERROR' | 'UNKNOWN';
  dataOrigin: 'MOCK' | 'BACKEND';
}

export interface LatestTradeSummary {
  entry: string | null;
  stopLoss: string | null;
  rangeHigh: string | null;
  remainingPosition: string | null;
  realizedPnl: string | null;
}

export type AccountStatus = 'CONNECTED' | 'AUTH_MISSING' | 'ERROR' | 'UNKNOWN';
export type AutoEarnStatus = 'ON' | 'OFF' | 'UNKNOWN';
export type LiraPreference = 'ENABLED' | 'DISABLED' | null;

export interface DashboardSnapshot {
  bot: {
    status: BotStatus;
    mode: ExecutionMode;
    startedAt: string | null;
  };
  strategy: StrategyProfile;
  strategyState: StrategyState;
  market: MarketSummary;
  accountAuth: AccountStatus;
  autoEarn: AutoEarnStatus;
  liraAutoEarn: {
    status: 'UNKNOWN';
    verified: false;
    apiVerification: 'NOT_EXPOSED' | 'UNKNOWN';
    userPreference: LiraPreference;
  };
  lastMarketUpdate: string | null;
  lastPrivateUpdate: string | null;
  balance: string | null;
  latestTrade: LatestTradeSummary | null;
  events: AgentEvent[];
}

export interface BacktestMetrics {
  totalTrades: string;
  winRate: string;
  profitFactor: string;
  averageR: string;
  expectancy: string;
  maxDrawdown: string;
  endingEquity: string;
}

export interface EquityPoint {
  at: string;
  equity: string;
}

export interface BacktestTrade {
  id: string;
  date: string;
  entry: string;
  exit: string;
  rMultiple: string;
  pnl: string;
  exitReason: string;
}

export interface BacktestResult {
  completedAt: string;
  metrics: BacktestMetrics;
  equityCurve: EquityPoint[];
  trades: BacktestTrade[];
}

export function createDefaultStrategy(): StrategyProfile {
  return {
    schemaVersion: 'strategy-config-v1',
    profileId: 'STRATEGY_V1',
    timeframes: {
      bias: '4H',
      range: '1H',
      entry: '15m',
    },
    entry: {
      level: 'FVG_EQ',
      secondaryFvgSupport: true,
    },
    risk: {
      riskPct: '1',
      minimumRR: '1',
    },
    management: {
      breakEvenEnabled: true,
      breakEvenTriggerR: '1',
      trailingEnabled: true,
      trailingBuffer: '',
    },
    exits: {
      partialTakeProfits: [],
      runnerPct: '10',
    },
    executionMode: 'PAPER',
  };
}

export function strategyName(): string {
  return 'Multi-Timeframe Trading Strategy';
}
