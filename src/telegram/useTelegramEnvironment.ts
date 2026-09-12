import { useEffect, useState } from 'react';
import { initTelegram } from './webapp.ts';
/** Browser rendering never waits on Telegram's optional network script. */
export function useTelegramEnvironment(): 'TELEGRAM' | 'BROWSER' {
  const [environment, setEnvironment] = useState<'TELEGRAM' | 'BROWSER'>('BROWSER');
  useEffect(() => {
    const initialize = () => setEnvironment(initTelegram(window.Telegram?.WebApp).environment);
    const script = document.getElementById('telegram-webapp-sdk');
    script?.addEventListener('load', initialize);
    initialize();
    return () => script?.removeEventListener('load', initialize);
  }, []);
  return environment;
}
