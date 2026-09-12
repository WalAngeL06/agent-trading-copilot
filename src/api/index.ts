import { createMockApi } from './mock.ts';
import type { ProfileStorage } from './mock.ts';
let storage: ProfileStorage | undefined;
try { storage = window.localStorage; } catch { /* Browser may block local storage. */ }
/** Replace this factory with a backend adapter; preserve TradingControlApi. */
export const controlApi = createMockApi(storage);
