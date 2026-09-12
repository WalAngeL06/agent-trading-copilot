export type IconName = 'dashboard' | 'strategy' | 'play' | 'stop' | 'chevron'
  | 'shield' | 'activity' | 'back' | 'bot' | 'check' | 'warning';
const paths: Record<IconName, React.ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  strategy: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor"/><circle cx="16" cy="12" r="2" fill="currentColor"/><circle cx="8" cy="18" r="2" fill="currentColor"/></>,
  play: <path d="m8 4 12 8-12 8Z"/>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2"/>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4"/>,
  back: <path d="m14 5-7 7 7 7"/>,
  bot: <><rect x="4" y="7" width="16" height="13" rx="4"/><path d="M12 3v4M2 12v4M22 12v4M8 16h8"/><path d="M8 11v1M16 11v1"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  warning: <><path d="m12 3 10 18H2Z"/><path d="M12 9v4M12 17h.01"/></>,
};
export function Icon({name, size = 20}: {name: IconName; size?: number}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true">{paths[name]}</svg>;
}
