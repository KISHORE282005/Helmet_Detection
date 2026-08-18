/** Top header: where you are, whether the system is live, and the alert queue. */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useHealth, useNotifications } from '../../lib/hooks';
import { confidencePercent, relativeTime, shortDate } from '../../lib/format';
import { mediaUrl } from '../../lib/api';
import { AlertIcon, Badge, Button, EmptyState, StatusDot, cx } from '../ui/primitives';

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

export function TopBar() {
  const now = useClock();
  const health = useHealth();
  const notifications = useNotifications();
  const [panelOpen, setPanelOpen] = useState(false);

  const unread = notifications.data?.unread ?? 0;
  const mode = health.data?.mode;
  const healthy = health.data?.healthy;

  // "LIVE SYSTEM" must mean something. It reflects the server actually
  // answering health checks, and it names which input mode is running.
  const liveTone = health.isError ? 'critical' : healthy ? 'good' : 'warning';
  const liveLabel = health.isError
    ? 'SYSTEM UNREACHABLE'
    : mode === 'live'
      ? 'LIVE SYSTEM'
      : 'SYSTEM ONLINE';

  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-4 border-b border-line bg-surface px-4">
      <Button
        variant="ghost"
        size="sm"
        className="hidden"
        aria-label="Open navigation"
      >
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
        </svg>
      </Button>

      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold tracking-tight text-ink">
          Safety Operations Center
        </h1>
        <p className="hidden truncate text-[11px] text-ink-3 sm:block">
          AI-Powered Industrial PPE Safety Monitoring
        </p>
      </div>

      <div className="ml-auto flex items-center gap-3 sm:gap-5">
        <div
          className={cx(
            'hidden items-center gap-2 rounded border px-2.5 py-1 md:flex',
            liveTone === 'good' && 'border-good/30 bg-good/8',
            liveTone === 'warning' && 'border-warning/30 bg-warning/8',
            liveTone === 'critical' && 'border-critical/35 bg-critical/8',
          )}
          title={
            health.data
              ? `${health.data.components.filter((c) => c.status === 'online').length} of ${health.data.components.length} components online`
              : 'Contacting the AI server'
          }
        >
          <StatusDot tone={liveTone} pulse={liveTone === 'good'} />
          <span
            className={cx(
              'text-[10px] font-semibold tracking-wider',
              liveTone === 'good' && 'text-good',
              liveTone === 'warning' && 'text-warning',
              liveTone === 'critical' && 'text-critical',
            )}
          >
            {liveLabel}
          </span>
        </div>

        <div className="text-right leading-tight">
          <div className="text-[11px] text-ink-3">
            {shortDate(now.toISOString())}
          </div>
          <div className="tabular text-[13px] font-semibold text-ink">
            {now.toLocaleTimeString('en-GB', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
              hour12: true,
            })}
          </div>
        </div>

        <div className="relative">
          <button
            type="button"
            onClick={() => setPanelOpen((open) => !open)}
            className="relative flex h-8 w-8 items-center justify-center rounded border border-line-strong bg-surface-2 text-ink-2 transition-colors hover:text-ink"
            aria-label={`Notifications${unread ? `, ${unread} unreviewed` : ''}`}
            aria-expanded={panelOpen}
          >
            <BellIcon className="h-4 w-4" />
            {unread > 0 && (
              <span className="tabular absolute -right-1.5 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-critical px-1 text-[9px] font-bold text-white">
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </button>
          {panelOpen && (
            <NotificationPanel onClose={() => setPanelOpen(false)} />
          )}
        </div>

        <div className="flex items-center gap-2.5 border-l border-line pl-3 sm:pl-5">
          <div className="hidden text-right leading-tight sm:block">
            <div className="text-[12px] font-medium text-ink">Safety Supervisor</div>
            <div className="text-[10px] text-ink-3">EHS Department</div>
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-line-strong bg-surface-2 text-[11px] font-semibold text-ink-2">
            SS
          </div>
          <Link
            to="/settings"
            className="flex h-8 w-8 items-center justify-center rounded border border-line-strong bg-surface-2 text-ink-2 transition-colors hover:text-ink"
            aria-label="Settings"
          >
            <GearIcon className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const { data, isLoading } = useNotifications();

  return (
    <>
      <div className="fixed inset-0 z-10" onClick={onClose} role="presentation" />
      <div className="absolute right-0 top-10 z-20 flex max-h-[70vh] w-[340px] flex-col overflow-hidden rounded-lg border border-line-strong bg-surface shadow-2xl">
        <header className="flex items-center justify-between border-b border-line px-3 py-2.5">
          <div>
            <h3 className="text-[13px] font-semibold text-ink">Notification Center</h3>
            <p className="text-[10px] text-ink-3">
              {data ? `${data.unread} awaiting review · ${data.today} today` : 'Loading…'}
            </p>
          </div>
          <Link to="/violations" onClick={onClose}>
            <Button size="sm" variant="ghost">
              View all
            </Button>
          </Link>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading && <div className="p-4 text-xs text-ink-3">Loading notifications…</div>}
          {data && data.items.length === 0 && (
            <EmptyState
              compact
              icon={<AlertIcon className="h-5 w-5" />}
              title="No violations awaiting review"
              description="New helmet violations appear here as soon as the AI confirms them."
            />
          )}
          <ul className="divide-y divide-line">
            {data?.items.map((item) => (
              <li key={item.id}>
                <Link
                  to={`/incidents/${item.id}`}
                  onClick={onClose}
                  className="flex gap-3 px-3 py-2.5 transition-colors hover:bg-surface-2"
                >
                  {item.evidence ? (
                    <img
                      src={mediaUrl('evidence', item.evidence)}
                      alt=""
                      loading="lazy"
                      className="h-12 w-16 shrink-0 rounded border border-line object-cover"
                    />
                  ) : (
                    <div className="flex h-12 w-16 shrink-0 items-center justify-center rounded border border-line bg-surface-2 text-ink-3">
                      <AlertIcon className="h-4 w-4" />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <Badge tone="critical" icon={<AlertIcon className="h-2.5 w-2.5" />}>
                        {item.title}
                      </Badge>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-ink-2">
                      {item.camera_id} · {item.location || item.camera_name}
                    </p>
                    <p className="tabular mt-0.5 text-[10px] text-ink-3">
                      {item.video_time} · {relativeTime(item.detected_at)} ·{' '}
                      {confidencePercent(item.confidence)} confidence
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {data && (
          <footer className="border-t border-line px-3 py-2">
            <div className="eyebrow pb-1.5">Delivery channels</div>
            <div className="flex flex-wrap gap-1.5">
              {data.channels.map((channel) => (
                <Badge
                  key={channel.name}
                  tone={
                    channel.status === 'active'
                      ? 'good'
                      : channel.status === 'disabled'
                        ? 'neutral'
                        : 'accent'
                  }
                >
                  {channel.name}
                  {channel.status !== 'active' && ` · ${channel.status}`}
                </Badge>
              ))}
            </div>
          </footer>
        )}
      </div>
    </>
  );
}

function BellIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8.6a6 6 0 1 0-12 0c0 6-2.2 7.4-2.2 7.4h16.4S18 14.6 18 8.6Z" />
      <path d="M13.7 19.4a2 2 0 0 1-3.4 0" />
    </svg>
  );
}

function GearIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3.1" />
      <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z" />
    </svg>
  );
}
