import { useEffect, useState } from 'react';
import type { EntryLevel, PartialTakeProfit, StrategyProfile } from '../types/control.ts';
import { ENTRY_LEVELS, TIMEFRAMES } from '../types/control.ts';
import { allocationSummary } from '../api/strategyDraft.ts';
import { Card } from '../components/Card.tsx';
import { Icon } from '../components/Icon.tsx';
import { StatusBadge } from '../components/StatusBadge.tsx';

type TimeframeRole = keyof StrategyProfile['timeframes'];
const roles: Array<{ id: TimeframeRole; label: string; detail: string }> = [
  { id: 'bias', label: 'Bias TF', detail: 'Higher-timeframe direction' },
  { id: 'range', label: 'Range TF', detail: 'Range and manipulation context' },
  { id: 'entry', label: 'Entry TF', detail: 'FVG entry confirmation' },
];

const entryLabels: Record<EntryLevel, string> = {
  FVG_LOW: 'FVG LOW',
  FVG_EQ: 'EQ',
  FVG_HIGH: 'FVG HIGH',
};

function nextTargetId(targets: PartialTakeProfit[]): string {
  let sequence = targets.length + 1;
  while (targets.some(target => target.id === 'tp-' + sequence)) sequence += 1;
  return 'tp-' + sequence;
}

export function StrategySettings({ saved, running, onDirtyChange, onSave }: {
  saved: StrategyProfile;
  running: boolean;
  onDirtyChange: (dirty: boolean) => void;
  onSave: (profile: StrategyProfile) => Promise<StrategyProfile>;
}) {
  const [draft, setDraft] = useState<StrategyProfile>(() => structuredClone(saved));
  const [baseline, setBaseline] = useState(() => JSON.stringify(saved));
  const [saving, setSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [message, setMessage] = useState('');
  const [saveError, setSaveError] = useState('');
  const locked = saving || running;
  const dirty = JSON.stringify(draft) !== baseline;
  const errors: Record<string, string> = {}; // Domain errors come from the settings API.
  const allocation = allocationSummary(draft);

  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  useEffect(() => {
    if (!dirty) {
      setDraft(structuredClone(saved));
      setBaseline(JSON.stringify(saved));
    }
  }, [saved, dirty]);

  function change(next: StrategyProfile) {
    setDraft(next);
    setMessage('');
    setSaveError('');
  }

  function updateTarget(index: number, patch: Partial<PartialTakeProfit>) {
    change({
      ...draft,
      exits: {
        ...draft.exits,
        partialTakeProfits: draft.exits.partialTakeProfits.map((target, targetIndex) =>
          targetIndex === index ? { ...target, ...patch } : target),
      },
    });
  }

  function addTarget() {
    const id = nextTargetId(draft.exits.partialTakeProfits);
    change({
      ...draft,
      exits: {
        ...draft.exits,
        partialTakeProfits: [
          ...draft.exits.partialTakeProfits,
          {
            id,
            rMultiple: String(draft.exits.partialTakeProfits.length + 1),
            closePct: '',
          },
        ],
      },
    });
  }

  function removeTarget(index: number) {
    change({
      ...draft,
      exits: {
        ...draft.exits,
        partialTakeProfits: draft.exits.partialTakeProfits.filter((_, targetIndex) =>
          targetIndex !== index),
      },
    });
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    setMessage('');
    setSaveError('');
    if (Object.keys(errors).length || saving || running) return;
    setSaving(true);
    try {
      const result = await onSave(draft);
      setDraft(structuredClone(result));
      setBaseline(JSON.stringify(result));
      setMessage('Strategy saved.');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Strategy could not be saved. Try again.');
    } finally {
      setSaving(false);
    }
  }

  return <div className="strategy-page">
    <div className="page-heading page-heading--terminal">
      <div>
        <span className="eyebrow">STRATEGY</span>
        <h1>Strategy settings</h1>
        <p>Multi-Timeframe Trading Strategy</p>
      </div>
      <StatusBadge tone={dirty ? 'warning' : 'neutral'} dot>
        {dirty ? 'UNSAVED' : 'SAVED'}
      </StatusBadge>
    </div>

    {running && <p className="editing-notice" role="status">
      Stop the agent before modifying the active strategy.
    </p>}

    <form onSubmit={save} noValidate>
      <div className="strategy-summary">
        <div><span>Profile</span><strong>Multi-Timeframe Trading Strategy</strong></div>
        <div><span>Execution</span><strong className="paper-text">PAPER</strong></div>
        <div><span>Persistence</span><strong>LOCAL FILE</strong></div>
      </div>

      <div className="settings-grid">
        <Card className="timeframes-card">
          <div className="card-heading">
            <div><span className="eyebrow">CONTEXT</span><h2>Timeframe routing</h2></div>
            <Icon name="strategy" size={18}/>
          </div>
          <div className="timeframe-fields">
            {roles.map(role => <label key={role.id} className="field">
              <span>{role.label}</span>
              <select
                value={draft.timeframes[role.id]}
                disabled={locked}
                onChange={event => change({
                  ...draft,
                  timeframes: {
                    ...draft.timeframes,
                    [role.id]: event.target.value,
                  },
                })}
              >
                {TIMEFRAMES.map(timeframe => <option key={timeframe}>{timeframe}</option>)}
              </select>
              <small>{role.detail}</small>
            </label>)}
          </div>
        </Card>

        <Card className="entry-card">
          <div className="card-heading">
            <div><span className="eyebrow">SETUP</span><h2>FVG entry</h2></div>
            <StatusBadge tone="neutral">DEFAULT EQ</StatusBadge>
          </div>
          <span className="field-label">Entry level</span>
          <div className="segmented-control" role="group" aria-label="FVG entry level">
            {ENTRY_LEVELS.map(level => <button
              key={level}
              type="button"
              disabled={locked}
              aria-pressed={draft.entry.level === level}
              className={draft.entry.level === level
                ? 'segment-button segment-button--active'
                : 'segment-button'}
              onClick={() => change({
                ...draft,
                entry: { ...draft.entry, level },
              })}
            >{entryLabels[level]}</button>)}
          </div>
          <div className="toggle-row">
            <div>
              <label htmlFor="secondary-fvg">Secondary FVG support</label>
              <span>Allow a supporting FVG in the entry model.</span>
            </div>
            <input
              id="secondary-fvg"
              type="checkbox"
              role="switch"
              className="switch"
              checked={draft.entry.secondaryFvgSupport}
              disabled={locked}
              onChange={event => change({
                ...draft,
                entry: {
                  ...draft.entry,
                  secondaryFvgSupport: event.target.checked,
                },
              })}
            />
          </div>
          <p className="helper">Saved settings apply the next time you start the agent.</p>
        </Card>

        <Card className="risk-card">
          <div className="card-heading">
            <div><span className="eyebrow">CAPITAL</span><h2>Risk</h2></div>
            <Icon name="shield" size={18}/>
          </div>
          <div className="field-grid">
            <label className="field">
              <span>Risk %</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.0001"
                  max="100"
                  step="0.0001"
                  value={draft.risk.riskPct}
                  disabled={locked}
                  aria-invalid={submitted && Boolean(errors.riskPct)}
                  onChange={event => change({
                    ...draft,
                    risk: { ...draft.risk, riskPct: event.target.value },
                  })}
                />
                <span>%</span>
              </div>
              {submitted && errors.riskPct && <small className="field-error">{errors.riskPct}</small>}
            </label>
            <label className="field">
              <span>Minimum RR</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.0001"
                  step="0.0001"
                  value={draft.risk.minimumRR}
                  disabled={locked}
                  aria-invalid={submitted && Boolean(errors.minimumRR)}
                  onChange={event => change({
                    ...draft,
                    risk: { ...draft.risk, minimumRR: event.target.value },
                  })}
                />
                <span>R</span>
              </div>
              {submitted && errors.minimumRR && <small className="field-error">{errors.minimumRR}</small>}
            </label>
          </div>
        </Card>

        <Card className="management-card">
          <div className="card-heading">
            <div><span className="eyebrow">POSITION</span><h2>Management</h2></div>
            <Icon name="trend" size={18}/>
          </div>
          <div className="management-block">
            <div className="toggle-row toggle-row--compact">
              <div><label htmlFor="break-even">Break Even</label><span>Move stop after the R trigger.</span></div>
              <StatusBadge tone="positive">ENABLED</StatusBadge>
            </div>
            <label className="field">
              <span>BE trigger R</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.0001"
                  step="0.0001"
                  value={draft.management.breakEvenTriggerR}
                  disabled={locked || !draft.management.breakEvenEnabled}
                  aria-invalid={submitted && Boolean(errors.breakEvenTriggerR)}
                  onChange={event => change({
                    ...draft,
                    management: {
                      ...draft.management,
                      breakEvenTriggerR: event.target.value,
                    },
                  })}
                />
                <span>R</span>
              </div>
              {submitted && errors.breakEvenTriggerR
                && <small className="field-error">{errors.breakEvenTriggerR}</small>}
            </label>
          </div>

          <div className="management-block">
            <div className="toggle-row toggle-row--compact">
              <div><label htmlFor="trailing">Trailing</label><span>Trail confirmed higher lows after break-even.</span></div>
              <input
                id="trailing"
                type="checkbox"
                role="switch"
                className="switch"
                checked={draft.management.trailingEnabled}
                disabled={locked}
                onChange={event => change({
                  ...draft,
                  management: {
                    ...draft.management,
                    trailingEnabled: event.target.checked,
                  },
                })}
              />
            </div>
            <label className="field">
              <span>Trailing buffer</span>
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step="0.0001"
                placeholder="Use backend default"
                value={draft.management.trailingBuffer}
                disabled={locked || !draft.management.trailingEnabled}
                aria-invalid={submitted && Boolean(errors.trailingBuffer)}
                onChange={event => change({
                  ...draft,
                  management: {
                    ...draft.management,
                    trailingBuffer: event.target.value,
                  },
                })}
              />
              {submitted && errors.trailingBuffer
                && <small className="field-error">{errors.trailingBuffer}</small>}
            </label>
          </div>
        </Card>

        <Card className="take-profit-card">
          <div className="card-heading">
            <div><span className="eyebrow">EXITS</span><h2>Partial take profits</h2></div>
            <StatusBadge tone={allocation.exceedsLimit ? 'danger' : 'positive'}>
              {allocation.allocatedPct}% ALLOCATED
            </StatusBadge>
          </div>

          <div className="tp-table">
            <div className="tp-header" aria-hidden="true">
              <span>Target</span><span>R multiple</span><span>Close %</span><span/>
            </div>
            {draft.exits.partialTakeProfits.map((target, index) => <div className="tp-row" key={target.id}>
              <strong>TP{index + 1}</strong>
              <label className="field field--compact">
                <span className="sr-only">{'TP' + (index + 1) + ' R Multiple'}</span>
                <div className="input-with-unit">
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0.0001"
                    step="0.0001"
                    aria-label={'TP' + (index + 1) + ' R Multiple'}
                    value={target.rMultiple}
                    disabled={locked}
                    aria-invalid={submitted && Boolean(errors['tp-' + index + '-r'])}
                    onChange={event => updateTarget(index, { rMultiple: event.target.value })}
                  />
                  <span>R</span>
                </div>
              </label>
              <label className="field field--compact">
                <span className="sr-only">{'TP' + (index + 1) + ' Close %'}</span>
                <div className="input-with-unit">
                  <input
                    type="number"
                    inputMode="decimal"
                    min="0.0001"
                    max="100"
                    step="0.0001"
                    aria-label={'TP' + (index + 1) + ' Close %'}
                    value={target.closePct}
                    disabled={locked}
                    aria-invalid={submitted && Boolean(errors['tp-' + index + '-close'])}
                    onChange={event => updateTarget(index, { closePct: event.target.value })}
                  />
                  <span>%</span>
                </div>
              </label>
              <button
                type="button"
                className="icon-button"
                aria-label={'Remove TP' + (index + 1)}
                disabled={locked}
                onClick={() => removeTarget(index)}
              ><Icon name="trash" size={16}/></button>
            </div>)}
          </div>

          <button type="button" className="add-target-button" disabled={locked} onClick={addTarget}>
            <Icon name="plus" size={16}/>Add take profit
          </button>

          <div className="runner-row">
            <div><strong>Runner</strong><span>Position reserved after partial exits.</span></div>
            <label className="field field--runner">
              <span className="sr-only">Runner %</span>
              <div className="input-with-unit">
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  max="100"
                  step="0.0001"
                  aria-label="Runner %"
                  value={draft.exits.runnerPct}
                  disabled={locked}
                  aria-invalid={submitted && Boolean(errors.runnerPct)}
                  onChange={event => change({
                    ...draft,
                    exits: { ...draft.exits, runnerPct: event.target.value },
                  })}
                />
                <span>%</span>
              </div>
            </label>
          </div>

          <div className={allocation.exceedsLimit
            ? 'allocation-meter allocation-meter--error'
            : 'allocation-meter'}
          >
            <div className="allocation-track">
              <span style={{
                width: allocation.exceedsLimit ? '100%' : allocation.allocatedPct + '%',
              }}/>
            </div>
            <div className="allocation-copy">
              <span>{allocation.allocatedPct}% allocated</span>
              <span>{allocation.exceedsLimit
                ? 'Over 100% limit'
                : allocation.remainingPct + '% remaining'}</span>
            </div>
          </div>
          {errors.allocation && <p className="allocation-error" role="alert">{errors.allocation}</p>}
        </Card>
      </div>

      <div className="save-area">
        {submitted && Object.keys(errors).length > 0 && <p className="field-error" role="alert">
          Review the highlighted strategy values before saving.
        </p>}
        {saveError && <p className="error-message" role="alert">{saveError}</p>}
        <div className="save-row">
          <p className="save-note" role="status" aria-live="polite">
            {message || 'Settings are saved on this machine and survive backend restarts.'}
          </p>
          <button className="button button--primary" type="submit" disabled={saving || running}>
            <Icon name="check" size={17}/>{saving ? 'Saving…' : 'Save Strategy'}
          </button>
        </div>
      </div>
    </form>
  </div>;
}
