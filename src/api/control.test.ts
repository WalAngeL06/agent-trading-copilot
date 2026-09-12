import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createMockApi } from './mock.ts';

test('starts and stops local bot state without invented decisions', async () => {
  const api = createMockApi();
  const initial = await api.getDashboard();
  assert.equal(initial.bot.status, 'STOPPED');
  const running = await api.startBot();
  assert.equal(running.bot.status, 'RUNNING');
  assert.equal(running.market.decision, initial.market.decision);
  assert.equal(running.market.dataOrigin, 'MOCK');
  assert.equal((await api.stopBot()).bot.status, 'STOPPED');
});
test('saves validated config, preserves strings and isolates callers', async () => {
  const saved = new Map<string, string>();
  const storage = { getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => { saved.set(key, value); } };
  const api = createMockApi(storage);
  const profile = await api.getStrategy();
  profile.risk.riskPerTradePct = '0.75';
  profile.timeframes.confirmation = '5m';
  await api.saveStrategy(profile);
  profile.risk.riskPerTradePct = '99';
  assert.equal((await api.getStrategy()).risk.riskPerTradePct, '0.75');
  assert.equal((await createMockApi(storage).getStrategy()).timeframes.confirmation, '5m');
  assert.equal((await createMockApi(storage).getDashboard()).bot.status, 'STOPPED');
});
test('rejects invalid risk and unavailable modules atomically', async () => {
  const api = createMockApi();
  const profile = await api.getStrategy();
  profile.risk.riskPerTradePct = '-1';
  await assert.rejects(api.saveStrategy(profile), /Risk per trade/);
  profile.risk.riskPerTradePct = '1';
  profile.conditions.range = true;
  await assert.rejects(api.saveStrategy(profile), /unavailable/);
  assert.equal((await api.getStrategy()).conditions.range, false);
});
test('LIVE is a preview and can never start execution', async () => {
  const api = createMockApi();
  const profile = await api.getStrategy();
  profile.executionMode = 'LIVE';
  await api.saveStrategy(profile);
  await assert.rejects(api.startBot(), /LIVE.*unavailable/);
  assert.equal((await api.getDashboard()).bot.status, 'STOPPED');
});
test('requires stopping before changing strategy', async () => {
  const api = createMockApi();
  await api.startBot();
  await assert.rejects(api.saveStrategy(await api.getStrategy()), /Stop/);
});
test('storage failure is atomic and corrupt config falls back safely', async () => {
  const broken = createMockApi({ getItem: () => null, setItem: () => { throw Error('quota'); } });
  const profile = await broken.getStrategy();
  profile.preset = 'CUSTOM';
  await assert.rejects(broken.saveStrategy(profile), /storage/);
  assert.equal((await broken.getStrategy()).preset, 'SWEEP_REVERSAL');
  const corrupted = createMockApi({ getItem: () => '{"executionMode":"LIVE"}', setItem: () => {} });
  assert.equal((await corrupted.getStrategy()).executionMode, 'ANALYZE');
});

test('rejects enum arrays from corrupt browser settings instead of coercing them', async () => {
  for (const field of ['preset', 'trailingStop', 'executionMode'] as const) {
    const baseline = await createMockApi().getStrategy();
    const malformed = { ...baseline, [field]: [field === 'executionMode' ? 'LIVE' : baseline[field]] };
    const api = createMockApi({ getItem: () => JSON.stringify(malformed), setItem: () => {} });
    assert.equal((await api.getStrategy()).executionMode, 'ANALYZE');
    assert.equal(typeof (await api.getStrategy())[field], 'string');
  }
});
