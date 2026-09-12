import { BackendApi } from './backend.ts';
import type { ProfileStorage } from './mock.ts';
let storage: ProfileStorage | undefined;
try { storage = window.localStorage; } catch { /* Browser may block local storage. */ }
export const controlApi = new BackendApi(storage);
