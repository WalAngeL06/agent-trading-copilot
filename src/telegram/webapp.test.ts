import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initTelegram } from './webapp.ts';
test('falls back without Telegram and with an unloaded SDK', () => {
  assert.equal(initTelegram().environment, 'BROWSER');
  assert.equal(initTelegram({}).environment, 'BROWSER');
});
test('initializes Telegram without reading auth data', () => {
  let ready = 0, expanded = 0;
  assert.equal(initTelegram({ platform: 'android', ready: () => { ready++; },
    expand: () => { expanded++; } }).environment, 'TELEGRAM');
  assert.equal(ready, 1);
  assert.equal(expanded, 1);
});
test('SDK failure does not crash the shell', () => {
  assert.equal(initTelegram({ platform: 'android', ready: () => { throw Error('SDK'); } })
    .environment, 'BROWSER');
});
