import { useCallback, useEffect, useRef, useState } from 'react';
import type { TradingControlApi } from './api/control.ts';
import type { DashboardSnapshot, StrategyProfile, LiraPreference } from './types/control.ts';
import { Dashboard } from './pages/Dashboard.tsx';
import { StrategySettings } from './pages/StrategySettings.tsx';
import { Icon } from './components/Icon.tsx';
import { ConfirmDialog } from './components/ConfirmDialog.tsx';
import { AccessGate } from './components/AccessGate.tsx';
import { AccessDeniedError, saveAccessKey } from './api/access.ts';

type Page = 'dashboard' | 'strategy';

export function App({ api, environment }: {
  api: TradingControlApi;
  environment: 'TELEGRAM' | 'BROWSER';
}) {
  const [data, setData] = useState<DashboardSnapshot | null>(null);
  const [page, setPage] = useState<Page>('dashboard');
  const [dirty, setDirty] = useState(false);
  const [pendingPage, setPendingPage] = useState<Page | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [accessRequired, setAccessRequired] = useState(false);
  const [keyRejected, setKeyRejected] = useState(false);
  const keySubmitted = useRef(false);
  const reportDirty = useCallback((value: boolean) => setDirty(value), []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await api.getDashboard());
      setAccessRequired(false);
    } catch (problem) {
      if (problem instanceof AccessDeniedError) {
        setAccessRequired(true);
        setKeyRejected(keySubmitted.current);
      } else setError('Control center could not load. Try again.');
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (busy || accessRequired) return;
    let active = true;
    let pending = false;
    const timer = window.setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        const snapshot = await api.getDashboard();
        if (active) { setData(snapshot); setError(''); }
      } catch (problem) {
        if (!active) return;
        if (problem instanceof AccessDeniedError) setAccessRequired(true);
        else setError('Backend unavailable. Displayed values are from the last successful read.');
      } finally { pending = false; }
    }, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [api, busy, accessRequired]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  function navigate(next: Page) {
    if (next === page) return;
    if (dirty) {
      setPendingPage(next);
      return;
    }
    setPage(next);
    setError('');
    window.scrollTo({ top: 0 });
  }

  async function agentAction(action: 'start' | 'stop') {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      setData(await (action === 'start' ? api.startBot() : api.stopBot()));
    } catch (problem) {
      if (problem instanceof AccessDeniedError) setAccessRequired(true);
      else setError(problem instanceof Error ? problem.message : 'Agent action failed. Try again.');
    } finally {
      setBusy(false);
    }
  }

  async function saveLiraPreference(preference: LiraPreference) {
    if (busy) return;
    setBusy(true);
    setError('');
    try { setData(await api.saveLiraPreference(preference)); }
    catch (problem) {
      if (problem instanceof AccessDeniedError) setAccessRequired(true);
      else setError(problem instanceof Error ? problem.message : 'Preference could not be saved.');
    }
    finally { setBusy(false); }
  }

  function unlock(key: string) {
    saveAccessKey(key);
    keySubmitted.current = true;
    setKeyRejected(false);
    void load();
  }

  async function saveStrategy(profile: StrategyProfile): Promise<StrategyProfile> {
    setBusy(true);
    try {
      const saved = await api.saveStrategy(profile);
      setData(await api.getDashboard());
      return saved;
    } finally { setBusy(false); }
  }

  return <div className="app-shell">
    <header className="app-header">
      <a
        className="brand"
        href="#dashboard"
        onClick={event => {
          event.preventDefault();
          navigate('dashboard');
        }}
      >
        <span className="brand-symbol"><Icon name="activity" size={22}/></span>
        <span className="brand-copy"><strong>Agent Trading</strong><small>Control terminal</small></span>
      </a>
      <div className="header-meta">
        <span className="paper-chip">PAPER</span>
        <span className="environment-label">
          {environment === 'TELEGRAM' ? 'Telegram Mini App' : 'Browser mode'}
        </span>
      </div>
    </header>

    <main id="main-content">
      {error && <div className="app-error" role="alert">
        <p>{error}</p>
        {!data && <button
          type="button"
          className="text-button"
          disabled={loading}
          onClick={() => void load()}
        >Try again</button>}
      </div>}

      {accessRequired
        ? <AccessGate telegram={environment === 'TELEGRAM'} rejected={keyRejected} onSubmit={unlock}/>
        : loading && !data
        ? <div className="loading-state" role="status">Loading control terminal…</div>
        : data && (
          page === 'dashboard'
            ? <Dashboard
              data={data}
              busy={busy || Boolean(error)}
              onStart={() => void agentAction('start')}
              onStop={() => void agentAction('stop')}
              onStrategy={() => navigate('strategy')}
              onLiraPreference={preference => void saveLiraPreference(preference)}
            />
            : <StrategySettings
                saved={data.strategy}
                running={data.bot.status === 'RUNNING' || Boolean(error)}
                onDirtyChange={reportDirty}
                onSave={saveStrategy}
              />
        )}
    </main>

    {!accessRequired && <nav className="bottom-nav" aria-label="Main navigation">
      <button
        type="button"
        className={page === 'dashboard' ? 'nav-item nav-item--active' : 'nav-item'}
        aria-current={page === 'dashboard' ? 'page' : undefined}
        onClick={() => navigate('dashboard')}
      >
        <Icon name="dashboard"/><span>Dashboard</span>
      </button>
      <button
        type="button"
        className={page === 'strategy' ? 'nav-item nav-item--active' : 'nav-item'}
        aria-current={page === 'strategy' ? 'page' : undefined}
        onClick={() => navigate('strategy')}
      >
        <Icon name="strategy"/><span>Strategy</span>
      </button>
    </nav>}

    {pendingPage && <ConfirmDialog
      title="Discard unsaved changes?"
      confirmLabel="Discard changes"
      onCancel={() => setPendingPage(null)}
      onConfirm={() => {
        setDirty(false);
        setPage(pendingPage);
        setPendingPage(null);
        setError('');
        window.scrollTo({ top: 0 });
      }}
    >
      <p>Your saved strategy will stay as it is. Changes on this screen will be discarded.</p>
    </ConfirmDialog>}
  </div>;
}
