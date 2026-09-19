const ACCESS_KEY_STORAGE = 'agent-trading.access-key';
let memoryKey: string | undefined;

/** The backend requires an access key or an allowed Telegram account. */
export class AccessDeniedError extends Error {
  constructor() {
    super('Access key required.');
    this.name = 'AccessDeniedError';
  }
}

export function buildAccessHeaders(initData?: string, accessKey?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (initData) headers['X-Telegram-Init-Data'] = initData;
  const key = accessKey?.trim();
  if (key) headers.Authorization = 'Bearer ' + key;
  return headers;
}

function storedAccessKey(): string | undefined {
  try { return globalThis.localStorage?.getItem(ACCESS_KEY_STORAGE) ?? memoryKey; }
  catch { return memoryKey; }
}

/** Keeps the key in this browser only; private mode falls back to this page's memory. */
export function saveAccessKey(key: string): void {
  memoryKey = key.trim();
  try { globalThis.localStorage?.setItem(ACCESS_KEY_STORAGE, memoryKey); } catch { /* memory only */ }
}

/** Telegram Mini App identity inside Telegram, plus the access key saved in this browser. */
export function browserAccessHeaders(): Record<string, string> {
  const telegram = (globalThis as { Telegram?: { WebApp?: { initData?: string } } }).Telegram;
  return buildAccessHeaders(telegram?.WebApp?.initData, storedAccessKey());
}
