import { test } from 'node:test';
import assert from 'node:assert/strict';
import { BackendApi } from './backend.ts';
import { createDefaultStrategy } from '../types/control.ts';

function transport() {
  let config = createDefaultStrategy();
  let running = false;
  let fail = false;
  const calls: string[] = [];
  const request = async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname;
    calls.push((init?.method ?? 'GET') + ' ' + path);
    if (fail) return new Response(JSON.stringify({error: {message: 'Stop the agent before modifying the active strategy.'}}), {status: 409});
    if (path.endsWith('/config')) {
      if (init?.method === 'PUT') config = {...JSON.parse(String(init.body)), risk: {riskPct: '0.75', minimumRR: '1'}};
      return Response.json(config);
    }
    if (path.endsWith('/start')) running = true;
    if (path.endsWith('/stop')) running = false;
    if (path.endsWith('/status')) return Response.json({bot_status: running ? 'running' : 'stopped', execution_mode: 'PAPER', market_status: 'WAITING', market_connected: false, market_source: 'OKX_ATK_MCP', account_auth: 'AUTH_MISSING', symbol: 'BTC-USDT', last_market_update: null, last_private_update: null});
    return Response.json({});
  };
  return {request: request as typeof fetch, calls, fail: () => {fail = true;}};
}

test('settings load from the backend and saves re-fetch persisted values', async () => {
  const wire = transport();
  const api = new BackendApi(undefined, 'http://localhost:8000', wire.request);
  assert.equal(api.strategyStorage, 'BACKEND');
  const profile = await api.getStrategy();
  profile.risk.riskPct = '0.7500';
  const saved = await api.saveStrategy(profile);
  assert.equal(saved.risk.riskPct, '0.75');
  assert.deepEqual(wire.calls, ['GET /api/v1/strategy/config', 'PUT /api/v1/strategy/config', 'GET /api/v1/strategy/config']);
});

test('server errors reach the caller and never claim a save', async () => {
  const wire = transport();
  wire.fail();
  const api = new BackendApi(undefined, 'http://localhost:8000', wire.request);
  await assert.rejects(api.saveStrategy(createDefaultStrategy()), /Stop the agent/);
  assert.deepEqual(wire.calls, ['PUT /api/v1/strategy/config']);
});

test('start and stop await server actions then refresh state', async () => {
  const wire = transport();
  const api = new BackendApi(undefined, 'http://localhost:8000', wire.request);
  assert.equal((await api.startBot()).bot.status, 'RUNNING');
  assert.equal(wire.calls[0], 'POST /api/v1/bot/start');
  assert.equal((await api.stopBot()).bot.status, 'STOPPED');
});

test('waiting market and missing account credentials are truthful', async () => {
  const wire = transport();
  const api = new BackendApi(undefined, 'http://localhost:8000', wire.request);
  const state = await api.getDashboard();
  assert.equal(state.market.connection, 'WAITING');
  assert.equal(state.accountAuth, 'AUTH_MISSING');
  assert.equal(state.autoEarn, 'UNKNOWN');
  assert.equal(state.market.lastPrice, null);
});

test('failed start does not refresh or create a running snapshot', async () => {
  const wire = transport(); wire.fail();
  const api = new BackendApi(undefined, 'http://localhost:8000', wire.request);
  await assert.rejects(api.startBot());
  assert.deepEqual(wire.calls, ['POST /api/v1/bot/start']);
});

test('transport outage does not fall back to browser or default configuration', async () => {
  const api = new BackendApi(undefined, 'http://localhost:8000', async () => {throw new Error('offline');});
  await assert.rejects(api.getStrategy(), /offline/);
  await assert.rejects(api.getDashboard(), /offline/);
});

test('invalid runtime status is rejected instead of inventing STOPPED or PAPER', async () => {
  const request = async () => Response.json({bot_status: 'unknown', execution_mode: 'LIVE'});
  const api = new BackendApi(undefined, 'http://localhost:8000', request);
  await assert.rejects(api.getDashboard(), /Unsupported runtime state/);
});
