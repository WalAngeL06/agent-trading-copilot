import type { StrategyProfile } from '../types/control.ts';

const DECIMAL = /^(?:0|[1-9]\d*)(?:\.\d{1,4})?$/;
const SCALE = 4;
const BASE = 10n ** BigInt(SCALE);

function toUnits(value: string): bigint | null {
  if (!DECIMAL.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * BASE + BigInt(fraction.padEnd(SCALE, '0'));
}

function fromUnits(value: bigint): string {
  const whole = value / BASE;
  const fraction = (value % BASE).toString().padStart(SCALE, '0').replace(/0+$/, '');
  return fraction ? whole.toString() + '.' + fraction : whole.toString();
}

export function allocationSummary(profile: StrategyProfile): {
  allocatedPct: string;
  remainingPct: string;
  exceedsLimit: boolean;
} {
  const values = [
    ...profile.exits.partialTakeProfits.map(target => target.closePct),
    profile.exits.runnerPct,
  ];
  const total = values.reduce<bigint>((sum, value) => sum + (toUnits(value) ?? 0n), 0n);
  const limit = 100n * BASE;
  return {
    allocatedPct: fromUnits(total),
    remainingPct: fromUnits(total >= limit ? 0n : limit - total),
    exceedsLimit: total > limit,
  };
}
