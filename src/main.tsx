import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.tsx';
import { controlApi } from './api/index.ts';
import { useTelegramEnvironment } from './telegram/useTelegramEnvironment.ts';
import './styles.css';
function Bootstrap() {
  const environment = useTelegramEnvironment();
  return <App api={controlApi} environment={environment}/>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><Bootstrap/></StrictMode>);
