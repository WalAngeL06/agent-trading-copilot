import type {
  AccountStatus,
  DashboardSnapshot,
  LiraPreference,
  StrategyState,
} from '../types/control.ts';
import { Card } from '../components/Card.tsx';
import { Icon } from '../components/Icon.tsx';
import { StatusBadge } from '../components/StatusBadge.tsx';

type BadgeTone = 'neutral' | 'positive' | 'warning' | 'danger';

function label(value: string): string {
  return value.replaceAll('_', ' ');
}

function stateTone(value: StrategyState): BadgeTone {
  if (value === 'TRADE_OPEN' || value === 'RUNNER_OPEN' || value === 'EXECUTED') return 'positive';
  if (value === 'BLOCKED') return 'danger';
  if (value.startsWith('WAITING') || value === 'WAIT' || value === 'PENDING_ENTRY') return 'warning';
  return 'neutral';
}

function accountTone(value: AccountStatus): BadgeTone {
  if (value === 'CONNECTED') return 'positive';
  if (value === 'ERROR') return 'danger';
  if (value === 'AUTH_MISSING') return 'warning';
  return 'neutral';
}

function timeLabel(at: string): string {
  const date = new Date(at);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function valueOrUnavailable(value: string | null | undefined): React.ReactNode {
  return value
    ? <strong className="trade-value">{value}</strong>
    : <span className="unavailable-value">Unavailable</span>;
}

export function Dashboard({ data, busy, onStart, onStop, onStrategy, onLiraPreference }: {
  data: DashboardSnapshot;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  onStrategy: () => void;
  onLiraPreference: (preference: LiraPreference) => void;
}) {
  const running = data.bot.status === 'RUNNING';
  const marketTone: BadgeTone = data.market.connection === 'CONNECTED'
    ? 'positive'
    : data.market.connection === 'ERROR'
      ? 'danger'
      : data.market.connection === 'RECONNECTING'
        ? 'warning'
        : 'neutral';
  const trade = data.latestTrade;

  return <div className="dashboard">
    <div className="page-heading page-heading--terminal">
      <div>
        <span className="eyebrow">OPERATIONS</span>
        <h1>Trading control center</h1>
        <p>Runtime health, strategy progress, and PAPER activity.</p>
      </div>
      <StatusBadge tone="neutral" dot>
        RUNTIME
      </StatusBadge>
    </div>

    <div className="runtime-strip" aria-label="Runtime status">
      <div className="runtime-stat">
        <span>Agent</span>
        <StatusBadge tone={running ? 'positive' : 'neutral'} dot>{data.bot.status}</StatusBadge>
      </div>
      <div className="runtime-stat">
        <span>Execution</span>
        <StatusBadge tone="warning">{data.bot.mode}</StatusBadge>
      </div>
      <div className="runtime-stat">
        <span>OKX</span>
        <StatusBadge tone={marketTone} dot>{data.market.connection}</StatusBadge>
      </div>
      <div className="runtime-stat">
        <span>Account</span>
        <StatusBadge tone={accountTone(data.accountAuth)}>{data.accountAuth}</StatusBadge>
      </div>
    </div>

    <div className="dashboard-grid">
      <Card className="agent-control-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">AGENT CONTROL</span>
            <h2>{running ? 'Market agent running' : 'Market agent stopped'}</h2>
          </div>
          <div className="bot-mark"><Icon name="bot" size={27}/></div>
        </div>
        <p className="card-copy">
          The agent processes closed market candles. Execution mode is PAPER.
        </p>
        <div className="bot-actions">
          <button
            type="button"
            className="button button--primary"
            disabled={busy || running}
            onClick={onStart}
          >
            <Icon name="play" size={16}/>{busy && !running ? 'Starting…' : 'Start Agent'}
          </button>
          <button
            type="button"
            className="button button--secondary"
            disabled={busy || !running}
            onClick={onStop}
          >
            <Icon name="stop" size={16}/>{busy && running ? 'Stopping…' : 'Stop Agent'}
          </button>
        </div>
      </Card>

      <Card className="strategy-state-card">
        <div className="card-heading">
          <span className="section-title">Strategy state</span>
          <Icon name="strategy" size={18}/>
        </div>
        <div className="state-display">{label(data.strategyState)}</div>
        <StatusBadge tone={stateTone(data.strategyState)} dot>{label(data.strategyState)}</StatusBadge>
        <div className="timeframe-preview">
          <span>Bias <b>{data.strategy.timeframes.bias}</b></span>
          <span>Range <b>{data.strategy.timeframes.range}</b></span>
          <span>Entry <b>{data.strategy.timeframes.entry}</b></span>
        </div>
        <button type="button" className="text-button" onClick={onStrategy}>
          Open Strategy <Icon name="chevron" size={15}/>
        </button>
      </Card>

      <Card className="market-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">MARKET</span>
            <h2>{data.market.symbol}</h2>
          </div>
          <span className="market-icon">₿</span>
        </div>
        <div className="market-price">
          <span>Last closed entry candle</span>
          {valueOrUnavailable(data.market.lastPrice)}
        </div>
        <div className="market-meta">
          <span>Last market update</span>
          <strong>{data.market.observedAt
            ? new Date(data.market.observedAt).toLocaleString()
            : 'Unavailable'}</strong>
        </div>
        <div className="market-meta"><span>Last private update</span><strong>{data.lastPrivateUpdate ? new Date(data.lastPrivateUpdate).toLocaleString() : 'WAITING'}</strong></div>
        <div className="market-meta"><span>Account equity (USD)</span>{valueOrUnavailable(data.balance)}</div>
      </Card>

      <Card className="atk-card">
        <div className="atk-heading">
          <div className="atk-icon"><Icon name="link" size={22}/></div>
          <div>
            <span className="eyebrow">INTEGRATION</span>
            <h2>OKX Agent Trade Kit</h2>
            <p>MCP Runtime</p>
          </div>
          <StatusBadge tone={marketTone} dot>
            {data.market.source === 'OKX_AGENT_TRADE_KIT_MCP' ? 'ATK' : 'UNAVAILABLE'}
          </StatusBadge>
        </div>
        <div className="capability-list">
          <div className="capability-row">
            <span><Icon name="database" size={16}/>Market Data</span>
            <StatusBadge tone={marketTone}>{data.market.connection}</StatusBadge>
          </div>
          <div className="capability-row">
            <span><Icon name="wallet" size={16}/>Account State</span>
            <StatusBadge tone={accountTone(data.accountAuth)}>{data.accountAuth}</StatusBadge>
          </div>
          <div className="capability-row">
            <span><Icon name="shield" size={16}/>Lira Auto Earn</span>
            <span>{data.liraAutoEarn.apiVerification === 'NOT_EXPOSED'
              ? 'API status not exposed' : 'Verification unavailable'}</span>
          </div>
          <div className="capability-row">
            <label htmlFor="lira-preference">Lira Auto Earn preference</label>
            <select id="lira-preference" disabled={busy}
              value={data.liraAutoEarn.userPreference ?? ''}
              onChange={event => onLiraPreference((event.target.value || null) as LiraPreference)}>
              <option value="">Not specified</option>
              <option value="ENABLED">ENABLED</option>
              <option value="DISABLED">DISABLED</option>
            </select>
          </div>
        </div>
        <p className="capability-note">Your local preference only. Not verified by OKX; changing it does not change your OKX account.</p>
        <p className="capability-note">Market source: OKX ATK / MCP</p>
      </Card>

      <Card className="trade-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">POSITION</span>
            <h2>Latest trade summary</h2>
          </div>
          <StatusBadge tone={trade ? 'neutral' : 'warning'}>
            {trade ? 'RUNTIME DATA' : 'UNAVAILABLE'}
          </StatusBadge>
        </div>
        <div className="trade-grid">
          <div><span>Entry</span>{valueOrUnavailable(trade?.entry)}</div>
          <div><span>SL</span>{valueOrUnavailable(trade?.stopLoss)}</div>
          <div><span>RangeHigh</span>{valueOrUnavailable(trade?.rangeHigh)}</div>
          <div><span>Remaining position</span>{valueOrUnavailable(trade?.remainingPosition)}</div>
          <div><span>Realized PnL</span>{valueOrUnavailable(trade?.realizedPnl)}</div>
        </div>
        {!trade && <p className="empty-inline">No trade summary has been reported.</p>}
      </Card>

      <Card className="activity-card">
        <div className="card-heading">
          <div>
            <span className="eyebrow">EVENTS</span>
            <h2>Agent activity</h2>
          </div>
          <Icon name="activity" size={18}/>
        </div>
        {data.events.length > 0
          ? <ol className="timeline">
            {data.events.map(event => <li
              key={event.id}
              className={'timeline-item timeline-item--' + event.tone}
            >
              <div className="timeline-dot"/>
              <div className="event-copy">
                <strong>{event.title}</strong>
                <p>{event.detail}</p>
              </div>
              <time dateTime={event.at} title={new Date(event.at).toLocaleString()}>
                {timeLabel(event.at)}
              </time>
            </li>)}
          </ol>
          : <div className="empty-list">
            <Icon name="activity" size={21}/>
            <span>No activity reported yet.</span>
          </div>}
        <p className="fine-print">
          Recent events from the connected service.
        </p>
      </Card>
    </div>
  </div>;
}
