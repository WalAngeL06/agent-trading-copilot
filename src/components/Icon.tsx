export type IconName =
  | 'dashboard'
  | 'strategy'
  | 'backtest'
  | 'play'
  | 'stop'
  | 'chevron'
  | 'shield'
  | 'activity'
  | 'back'
  | 'bot'
  | 'check'
  | 'warning'
  | 'database'
  | 'wallet'
  | 'link'
  | 'plus'
  | 'trash'
  | 'trend';

const paths: Record<IconName, React.ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
  strategy: <><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="currentColor"/><circle cx="16" cy="12" r="2" fill="currentColor"/><circle cx="8" cy="18" r="2" fill="currentColor"/></>,
  backtest: <><path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/></>,
  play: <path d="m8 4 12 8-12 8Z"/>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2"/>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/></>,
  activity: <path d="M3 12h4l3-8 4 16 3-8h4"/>,
  back: <path d="m14 5-7 7 7 7"/>,
  bot: <><rect x="4" y="7" width="16" height="13" rx="4"/><path d="M12 3v4M2 12v4M22 12v4M8 16h8"/><path d="M8 11v1M16 11v1"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  warning: <><path d="m12 3 10 18H2Z"/><path d="M12 9v4M12 17h.01"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  wallet: <><path d="M4 6h14a2 2 0 0 1 2 2v11H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h11"/><path d="M15 11h7v5h-7a2.5 2.5 0 0 1 0-5Z"/></>,
  link: <><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></>,
  trend: <><path d="M4 18 10 12l4 3 6-8"/><path d="M15 7h5v5"/></>,
};

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >{paths[name]}</svg>;
}
