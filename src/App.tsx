import { useCallback, useEffect, useState } from 'react';
import type { TradingControlApi } from './api/control.ts';
import type { DashboardSnapshot, StrategyProfile } from './types/control.ts';
import { Dashboard } from './pages/Dashboard.tsx';
import { StrategySettings } from './pages/StrategySettings.tsx';
import { Icon } from './components/Icon.tsx';
import { ConfirmDialog } from './components/ConfirmDialog.tsx';
type Page = 'dashboard' | 'strategy';
export function App({ api, environment }:
  { api: TradingControlApi; environment: 'TELEGRAM' | 'BROWSER' }) {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [page, setPage] = useState<Page>('dashboard');
  const [dirty, setDirty] = useState(false);
  const [pendingPage, setPendingPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const reportDirty = useCallback((value: boolean) => setDirty(value), []);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setData(await api.getDashboard()); }
    catch { setError('Control center could not load. Try again.'); }
    finally { setLoading(false); }
  }, [api]);
  useEffect(() => { void load(); }, [load]);
  const refresh = useCallback(async () => {
    // Silent live refresh: keep the last good snapshot when a poll fails.
    try { setData(await api.getDashboard()); } catch { /* keep current state */ }
  }, [api]);
  useEffect(() => {
    if (busy || dirty) return;
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh, busy, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  function navigate(next: Page) {
    if (next === page) return;
    if (dirty) { setPendingPage(next); return; }
    setPage(next); setError(''); window.scrollTo({top:0});
  }
  async function botAction(action: 'start' | 'stop') {
    if (busy) return;
    setBusy(true); setError('');
    try { setData(await (action === 'start' ? api.startBot() : api.stopBot())); }
    catch (problem) { setError(problem instanceof Error ? problem.message : 'Bot action failed. Try again.'); }
    finally { setBusy(false); }
  }
  async function saveStrategy(profile: StrategyProfile): Promise<StrategyProfile> {
    const saved = await api.saveStrategy(profile);
    setData(await api.getDashboard());
    return saved;
  }
  return <div className="app-shell">
    <header className="app-header"><a className="brand" href="#dashboard" onClick={event => {event.preventDefault();navigate('dashboard');}}>
      <span className="brand-symbol"><Icon name="activity" size={23}/></span><span>Agent Trading</span></a>
      <span className="environment-label">{environment === 'TELEGRAM' ? 'Telegram Mini App' : 'Browser mode'}</span>
    </header>
    <main id="main-content">
      <div className="demo-banner"><span className="demo-indicator"/><span>{api.kind === "MOCK" ? "Demo workspace · mock data, no execution" : "Connected workspace"}</span></div>
      {error && <div className="app-error" role="alert"><p>{error}</p>
        {!data && <button type="button" className="text-button" disabled={loading} onClick={() => void load()}>Try again</button>}</div>}
      {loading && !data ? <div className="loading-state" role="status">Loading control center…</div> : data &&
        (page === 'dashboard' ? <Dashboard data={data} busy={busy} isMock={api.kind === "MOCK"} onStart={() => void botAction('start')}
          onStop={() => void botAction('stop')} onStrategy={() => navigate('strategy')}/>
          : <StrategySettings saved={data.strategy} running={data.bot.status === 'RUNNING'}
            persistence={api.strategyStorage} isMock={api.kind === "MOCK"} onDirtyChange={reportDirty} onSave={saveStrategy}/>)}
    </main>
    <nav className="bottom-nav" aria-label="Main navigation">
      <button type="button" className={page === 'dashboard' ? 'nav-item nav-item--active' : 'nav-item'}
        aria-current={page === 'dashboard' ? 'page' : undefined} onClick={() => navigate('dashboard')}>
        <Icon name="dashboard"/><span>Dashboard</span></button>
      <button type="button" className={page === 'strategy' ? 'nav-item nav-item--active' : 'nav-item'}
        aria-current={page === 'strategy' ? 'page' : undefined} onClick={() => navigate('strategy')}>
        <Icon name="strategy"/><span>Strategy</span></button>
    </nav>
    {pendingPage && <ConfirmDialog title="Discard unsaved changes?" confirmLabel="Discard changes"
      onCancel={() => setPendingPage(null)} onConfirm={() => {
        setDirty(false);setPage(pendingPage);setPendingPage(null);setError('');window.scrollTo({top:0});
      }}><p>Your saved strategy will stay as it is. Changes on this screen will be discarded.</p></ConfirmDialog>}
  </div>;
}
