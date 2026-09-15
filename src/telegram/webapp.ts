export interface TelegramWebApp {
  platform?: string;
  ready?: () => void;
  expand?: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
}
declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp }; }
}
export function initTelegram(app?: TelegramWebApp): { environment: 'TELEGRAM' | 'BROWSER' } {
  // The SDK also exists in normal browsers; platform distinguishes a real WebView.
  if (!app?.platform || app.platform === 'unknown') return { environment: 'BROWSER' };
  try {
    app.ready?.();
    app.expand?.();
    app.setHeaderColor?.('#101214');
    app.setBackgroundColor?.('#101214');
    return { environment: 'TELEGRAM' };
  } catch { return { environment: 'BROWSER' }; }
}
