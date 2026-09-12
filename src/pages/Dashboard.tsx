import type { DashboardSnapshot, DecisionOutcome } from '../types/control.ts';
import { strategyName } from '../types/control.ts';
import { Card } from '../components/Card.tsx';
import { Icon } from '../components/Icon.tsx';
import { StatusBadge } from '../components/StatusBadge.tsx';
const decisions: Record<DecisionOutcome, string> = { NO_TRADE: 'NO TRADE', NO_SETUP: 'NO SETUP', WAIT: 'WAIT',
  TRADE_CANDIDATE: 'TRADE CANDIDATE', BLOCKED: 'BLOCKED', EXECUTED: 'EXECUTED' };
function timeLabel(at: string): string {
  return new Date(at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}
export function Dashboard({ data, busy, isMock, onStart, onStop, onStrategy }:
  { data: DashboardSnapshot; busy: boolean; isMock: boolean; onStart: () => void; onStop: () => void; onStrategy: () => void }) {
  const running = data.bot.status === 'RUNNING';
  const live = data.bot.mode === 'LIVE';
  return <div className="dashboard">
    <div className="page-heading">
      <div><h1>Control center</h1><p>Your agent, at a glance.</p></div>
      <StatusBadge tone={isMock ? "warning" : "neutral"}>{isMock ? "Local demo" : "Backend"}</StatusBadge>
    </div>
    <div className="dashboard-grid">
      <Card className="bot-card">
        <div className="card-heading"><span className="section-title">Bot status</span>
          <StatusBadge tone={running ? 'positive' : 'neutral'} dot>{data.bot.status}</StatusBadge></div>
        <div className="bot-headline"><div className="bot-mark"><Icon name="bot" size={30}/></div>
          <div><h2>{running ? 'Agent is running' : 'Agent is stopped'}</h2>
            <p>{live ? 'LIVE preview · execution unavailable' : data.bot.mode + (isMock ? ' mode · local preview' : ' mode')}</p></div></div>
        <div className="bot-actions">
          <button type="button" className="button button--primary" disabled={busy || running || live} onClick={onStart}>
            <Icon name="play" size={17}/>{busy && !running ? 'Starting…' : 'Start Bot'}</button>
          <button type="button" className="button button--secondary" disabled={busy || !running} onClick={onStop}>
            <Icon name="stop" size={17}/>{busy && running ? 'Stopping…' : 'Stop Bot'}</button>
        </div>
        <p className="fine-print">{live ? 'Choose ANALYZE or PAPER in Strategy to use demo controls.'
          : isMock ? 'Controls update this session. No market loop or orders.' : 'Bot controls use the connected service.'}</p>
      </Card>
      <Card className="market-card">
        <div className="card-heading"><span className="section-title">Current market</span><span className="subtle">Spot</span></div>
        <div className="market-heading"><h2>BTC<span>-USDT</span></h2><span className="market-icon">₿</span></div>
        <div className="decision-row"><span>Latest decision</span>
          <StatusBadge tone={data.market.decision === 'BLOCKED' || data.market.decision === 'WAIT' ? 'warning' : 'neutral'}>
            {data.market.decision ? decisions[data.market.decision] : 'UNAVAILABLE'}</StatusBadge></div>
        <p className="fine-print">{data.market.dataOrigin === "MOCK" ? "Sample decision · strategy engine disconnected." : data.market.decisionReason}</p>
        <div className="source-row"><span>Market data source</span><strong>{data.market.source}</strong></div>
        <div className="source-state"><span className="status-dot"/>{data.market.connection === 'DISCONNECTED'
          ? 'Not connected' : 'Connected'}</div>
      </Card>
      <Card className="strategy-card">
        <div className="card-heading"><span className="section-title">Active strategy</span><Icon name="strategy" size={18}/></div>
        <h2>{strategyName(data.strategy)}</h2>
        <div className="timeframe-preview"><span>Context <b>{data.strategy.timeframes.context}</b></span>
          <span>Setup <b>{data.strategy.timeframes.setup}</b></span>
          <span>Confirm <b>{data.strategy.timeframes.confirmation}</b></span></div>
        <button type="button" className="text-button" onClick={onStrategy}>Open Strategy<Icon name="chevron" size={16}/></button>
      </Card>
      <Card className="earn-card">
        <div className="card-heading"><span className="section-title">OKX Auto Earn</span>
          <StatusBadge tone={data.autoEarn === 'ON' ? 'positive' : 'neutral'}>{data.autoEarn}</StatusBadge></div>
        <h2>Account overview</h2>
        <p>Authenticated account reads are read-only.</p>
        <div className="earn-footer"><Icon name="shield" size={16}/><span>{data.accountAuth}</span></div>
      </Card>
      <Card className="activity-card">
        <div className="card-heading"><span className="section-title">Recent agent activity</span>
          <span className="subtle">{isMock ? "Local history" : "History"}</span></div>
        <ol className="timeline">
          {data.events.map(event => <li key={event.id} className={'timeline-item timeline-item--' + event.tone}>
            <div className="timeline-dot"/><div className="event-copy"><strong>{event.title}</strong><p>{event.detail}</p></div>
            <time dateTime={event.at} title={new Date(event.at).toLocaleString()}>{timeLabel(event.at)}</time>
          </li>)}
        </ol>
        <p className="fine-print">{isMock ? "Session activity resets on reload." : "Recent activity from the connected service."}</p>
      </Card>
    </div>
  </div>;
}
