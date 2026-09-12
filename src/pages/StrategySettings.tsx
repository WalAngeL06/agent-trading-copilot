import { useEffect, useState } from 'react';
import type { ExecutionMode, StrategyProfile } from '../types/control.ts';
import { CONDITIONS, TIMEFRAMES, createDefaultStrategy } from '../types/control.ts';
import { validateStrategy } from '../api/validation.ts';
import { Card } from '../components/Card.tsx';
import { Icon } from '../components/Icon.tsx';
import { StatusBadge } from '../components/StatusBadge.tsx';
import { ConfirmDialog } from '../components/ConfirmDialog.tsx';
type Role = keyof StrategyProfile['timeframes'];
const roles: {id: Role; label: string}[] = [
  {id:'context',label:'Context timeframe'}, {id:'structure',label:'Structure timeframe'},
  {id:'setup',label:'Setup timeframe'}, {id:'confirmation',label:'Confirmation timeframe'},
];
const modes: {id: ExecutionMode; description: string}[] = [
  {id:'ANALYZE', description:'Inspect only'}, {id:'PAPER',description:'Simulation preview'},
  {id:'LIVE',description:'Execution unavailable'},
];
export function StrategySettings({ saved, running, persistence, isMock, onDirtyChange, onSave }:
  { saved: StrategyProfile; running: boolean; persistence: 'BROWSER' | 'SESSION' | 'BACKEND'; isMock: boolean;
    onDirtyChange: (dirty: boolean) => void; onSave: (profile: StrategyProfile) => Promise<StrategyProfile> }) {
  const [draft, setDraft] = useState<StrategyProfile>(() => structuredClone(saved));
  const [saving, setSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState('');
  const [saveError, setSaveError] = useState('');
  const [liveDialog, setLiveDialog] = useState(false);
  const locked = saving || running;
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const errors = validateStrategy(draft);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  function change(next: StrategyProfile) { setDraft(next); setMessage(''); setSaveError(''); }
  function selectMode(mode: ExecutionMode) {
    if (mode === 'LIVE' && draft.executionMode !== 'LIVE') { setLiveDialog(true); return; }
    change({...draft, executionMode: mode});
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSubmitted(true); setMessage(''); setSaveError('');
    if (Object.keys(errors).length || saving || running) return;
    setSaving(true);
    try {
      const result = await onSave(draft);
      setDraft(structuredClone(result));
      setMessage(persistence === 'BACKEND' ? 'Strategy saved.' : persistence === 'BROWSER' ? 'Strategy saved in this browser.' : 'Strategy saved for this session only.');
    } catch (error) { setSaveError(error instanceof Error ? error.message : 'Strategy could not be saved. Try again.'); }
    finally { setSaving(false); }
  }
  return <div className="strategy-page">
    <div className="page-heading"><div><h1>Strategy settings</h1><p>Configure how your agent operates.</p></div>
      <StatusBadge tone={dirty ? 'warning' : 'neutral'}>{dirty ? 'Unsaved' : isMock ? 'Local config' : 'Saved config'}</StatusBadge></div>
    <form onSubmit={save} noValidate>
      {running && <p className="editing-notice" role="status">Bot is running. Stop it on Dashboard to edit the strategy.</p>}
      <div className="settings-grid">
        <Card className="preset-card">
          <div className="card-heading"><h2>Strategy profile</h2><Icon name="strategy" size={18}/></div>
          <label className="field"><span>Preset</span>
            <select value={draft.preset} disabled={locked} onChange={event => {
              change(event.target.value === 'SWEEP_REVERSAL' ? createDefaultStrategy() : {...draft,preset:'CUSTOM'});
            }}><option value="SWEEP_REVERSAL">Sweep Reversal</option><option value="CUSTOM">Custom</option></select></label>
          <p className="helper">{isMock ? "Editable demo preset. No strategy algorithm is connected." : "Strategy requirements are separate from display settings."}</p>
          <div className="field-grid timeframes">{roles.map(role => <label key={role.id} className="field">
            <span>{role.label}</span><select value={draft.timeframes[role.id]} disabled={locked}
              onChange={event => change({...draft,timeframes:{...draft.timeframes,
                [role.id]:event.target.value}})}>
              {TIMEFRAMES.map(tf => <option key={tf}>{tf}</option>)}</select>
          </label>)}</div>
          <p className="helper">These are strategy roles, independent of any future chart display.</p>
        </Card>
        <Card className="conditions-card">
          <div className="card-heading"><h2>Confirmation modules</h2></div>
          <p className="helper">{isMock ? "Switches save local configuration only. Backend algorithms are not integrated." : "Module availability is controlled by the adapter."}</p>
          <div className="condition-list">{CONDITIONS.map(module => <div key={module.id} className="condition-row">
            <div className="condition-copy"><label htmlFor={'condition-' + module.id}>{module.label}</label>
              <span>{module.configurable ? module.description + ' · demo only' : module.availability}</span></div>
            <input id={'condition-' + module.id} type="checkbox" role="switch"
              className="switch" checked={draft.conditions[module.id]}
              disabled={!module.configurable || locked}
              aria-describedby={!module.configurable ? 'unavailable-note' : undefined}
              onChange={event => change({...draft,conditions:{...draft.conditions,[module.id]:event.target.checked}})}/>
          </div>)}</div>
          <p className="helper" id="unavailable-note">Unavailable modules cannot be enabled.</p>
        </Card>
        <Card className="risk-card">
          <div className="card-heading"><h2>Risk limits</h2><Icon name="shield" size={18}/></div>
          <p className="helper">{isMock ? "Demo preferences. Limits are not enforced by a risk engine." : "Configure risk limits for this strategy."}</p>
          <div className="field-grid">
            {(['riskPerTradePct','maxDailyLossPct'] as const).map(key => <label className="field" key={key}>
              <span>{key === 'riskPerTradePct' ? 'Risk per trade %' : 'Max daily loss %'}</span>
              <input type="number" inputMode="decimal" min="0.0001" max="100" step="0.0001"
                value={draft.risk[key]} disabled={locked}
                aria-label={key === "riskPerTradePct" ? "Risk per trade %" : "Max daily loss %"} aria-invalid={submitted && Boolean(errors[key])}
                aria-describedby={submitted && errors[key] ? key + '-error' : undefined}
                onChange={event => change({...draft,risk:{...draft.risk,[key]:event.target.value}})}/>
              {submitted && errors[key] && <span className="field-error" id={key + '-error'}>{errors[key]}</span>}
            </label>)}
            <label className="field"><span>Max open positions</span>
              <input type="number" inputMode="numeric" min="1" max="100" step="1" disabled={locked}
                aria-label="Max open positions"
                value={Number.isNaN(draft.risk.maxOpenPositions) ? '' : draft.risk.maxOpenPositions}
                aria-invalid={submitted && Boolean(errors.maxOpenPositions)}
                aria-describedby={submitted && errors.maxOpenPositions ? 'positions-error' : undefined}
                onChange={event => change({...draft,risk:{...draft.risk,maxOpenPositions:
                  event.target.value === '' ? NaN : Number(event.target.value)}})}/>
              {submitted && errors.maxOpenPositions && <span className="field-error" id="positions-error">{errors.maxOpenPositions}</span>}
            </label>
            <label className="field"><span>Trailing Stop</span>
              <select value={draft.trailingStop} disabled={locked} onChange={event => change({...draft,
                trailingStop:event.target.value as StrategyProfile['trailingStop']})}>
                <option value="OFF">Off</option><option value="SWING_BASED">Swing Based</option>
                <option value="ATR_BASED">ATR Based</option></select></label>
          </div>
          <p className="helper">Swing and ATR trailing are configuration previews.</p>
        </Card>
        <Card className="execution-card">
          <div className="card-heading"><h2>Execution mode</h2><StatusBadge tone="warning">Preview only</StatusBadge></div>
          <div className="mode-selector" role="group" aria-label="Execution mode">{modes.map(mode =>
            <button type="button" key={mode.id} disabled={locked} aria-pressed={draft.executionMode === mode.id}
              className={'mode-option ' + (draft.executionMode === mode.id ? 'mode-option--selected ' : '')
                + (mode.id === 'LIVE' ? 'mode-option--live' : '')} onClick={() => selectMode(mode.id)}>
              <strong>{mode.id}</strong><span>{mode.description}</span></button>)}</div>
          {draft.executionMode === 'LIVE' ? <div className="warning-panel" role="status">
            <Icon name="warning" size={20}/><div><strong>LIVE execution is unavailable.</strong>
              <p>This saved preview cannot start the bot or send orders.</p></div></div>
            : <p className="helper">{draft.executionMode === 'PAPER'
              ? 'PAPER is a local preview. A simulator and fill tracking are not connected.'
              : 'ANALYZE is a local preview. No automatic evaluation or orders.'}</p>}
        </Card>
      </div>
      <div className="save-area">
        {running && <p className="warning-text" role="status">Stop the local bot on Dashboard before saving changes.</p>}
        {submitted && Object.keys(errors).length > 0 && <p className="field-error" role="alert">Fix the highlighted risk fields before saving.</p>}
        {saveError && <p className="error-message" role="alert">{saveError}</p>}
        <div className="save-row"><p className="save-note" role="status" aria-live="polite">{message ||
          (persistence === 'BACKEND' ? 'Strategy settings.' : persistence === 'BROWSER' ? 'Settings stay in this browser.' : 'Browser storage unavailable. Session-only settings.')}</p>
          <button className="button button--primary" type="submit" disabled={saving || running}>
            <Icon name="check" size={18}/>{saving ? 'Saving…' : 'Save Strategy'}</button></div>
      </div>
    </form>
    {liveDialog && <ConfirmDialog title="Confirm LIVE preview" confirmLabel="Confirm LIVE preview" danger
      acknowledgement="I understand this preview does not enable real execution."
      onCancel={() => setLiveDialog(false)} onConfirm={() => { change({...draft,executionMode:'LIVE'}); setLiveDialog(false); }}>
      <p>LIVE is intended for real exchange orders and carries financial risk.</p>
      <p>Real execution is unavailable in this shell. This selection only saves a local preference, and LIVE bot startup is blocked.</p>
    </ConfirmDialog>}
  </div>;
}
