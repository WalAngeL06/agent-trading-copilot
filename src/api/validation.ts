import { CONDITIONS, TIMEFRAMES } from '../types/control.ts';
const object = (value: unknown): Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
export function validateStrategy(value: unknown): Record<string, string> {
  const profile = object(value);
  const errors: Record<string, string> = {};
  if (profile.schemaVersion !== 'strategy-profile-local-v1')
    errors.profile = 'Strategy configuration version is unsupported.';
  if (typeof profile.preset !== 'string' || !['SWEEP_REVERSAL', 'CUSTOM'].includes(profile.preset))
    errors.preset = 'Choose a supported preset.';
  const timeframes = object(profile.timeframes);
  for (const role of ['context', 'structure', 'setup', 'confirmation']) {
    if (!(TIMEFRAMES as readonly unknown[]).includes(timeframes[role]))
      errors[role] = 'Choose a supported timeframe.';
  }
  const conditions = object(profile.conditions);
  for (const module of CONDITIONS) {
    if (typeof conditions[module.id] !== 'boolean')
      errors[module.id] = 'Confirmation values must be enabled or disabled.';
    else if (!module.configurable && conditions[module.id])
      errors[module.id] = module.label + ' is unavailable.';
  }
  const risk = object(profile.risk);
  for (const [key, label] of [['riskPerTradePct', 'Risk per trade'], ['maxDailyLossPct', 'Max daily loss']]) {
    const amount = risk[key];
    if (typeof amount !== 'string' || !/^(?:0|[1-9]\d*)(?:\.\d{1,4})?$/.test(amount)
      || Number(amount) <= 0 || Number(amount) > 100)
      errors[key] = label + ' must be above 0 and at most 100%, with up to 4 decimal places.';
  }
  if (typeof risk.maxOpenPositions !== 'number' || !Number.isInteger(risk.maxOpenPositions)
    || risk.maxOpenPositions < 1 || risk.maxOpenPositions > 100)
    errors.maxOpenPositions = 'Max open positions must be a whole number from 1 to 100.';
  if (typeof profile.trailingStop !== 'string' || !['SWING_BASED', 'ATR_BASED', 'OFF'].includes(profile.trailingStop))
    errors.trailingStop = 'Choose a supported trailing stop.';
  if (typeof profile.executionMode !== 'string' || !['ANALYZE', 'PAPER', 'LIVE'].includes(profile.executionMode))
    errors.executionMode = 'Choose a supported execution mode.';
  return errors;
}
export function assertValidStrategy(value: unknown): void {
  const errors = Object.values(validateStrategy(value));
  if (errors.length) throw new Error(errors[0]);
}
