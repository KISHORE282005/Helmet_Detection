/** Permanent left navigation, grouped the way a safety team thinks:
 *  what is happening now, what needs review, what gets reported, what runs it.
 */

import { NavLink } from 'react-router-dom';
import { cx } from '../ui/primitives';

interface NavItem {
  to: string;
  label: string;
  /** Live count rendered as a pill; only shown when non-zero. */
  badge?: number;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

export function Sidebar({
  openViolations,
  onNavigate,
  className,
  collapsed = false,
  onToggle,
}: {
  openViolations: number;
  onNavigate?: () => void;
  className?: string;
  collapsed?: boolean;
  onToggle?: () => void;
}) {

  const groups: NavGroup[] = [
    {
      title: 'Monitoring',
      items: [
        { to: '/', label: 'Dashboard' },
        { to: '/live', label: 'Live Cameras' },
        
        { to: '/analysis', label: 'Video Analysis' },
      ],
    },
    {
      title: 'Safety',
      items: [
        { to: '/violations', label: 'Active Violations', badge: openViolations },
        { to: '/incidents', label: 'Incident History' },
        
      ],
    },
    {
      title: 'Productivity',
      items: [{ to: '/nva', label: 'NVA Analysis' }],
    },
    {
      title: 'Reports',
      items: [
        { to: '/reports', label: 'Safety Reports' },
        
      ],
    },
    {
      title: 'System',
      items: [
        { to: '/cameras', label: 'Cameras' },
       
        { to: '/settings', label: 'Settings' },
      ],
    },
  ];


  // The three the operator is asked to trust at a glance.

  return (
    <aside
      className={cx(
        'flex h-full shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-200',
        collapsed ? 'w-12' : 'w-60',
        className,
      )}
    >
      <div className="flex items-center gap-2.5 border-b border-line px-3 py-3.5">
        {!collapsed && <Logo />}
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="truncate text-[15px] leading-tight font-semibold tracking-tight text-ink">
              SafeVision <span className="text-accent">AI</span>
            </div>
            <div className="truncate text-[10px] text-ink-3">Industrial Safety Intelligence</div>
          </div>
        )}
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            className={cx(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded border border-line-strong bg-surface-2 text-ink-2 transition-colors hover:bg-surface hover:text-ink',
              collapsed && 'mx-auto',
            )}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg
              viewBox="0 0 24 24"
              className={cx('h-4 w-4 transition-transform duration-200', collapsed && 'rotate-180')}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              {collapsed ? (
                <path d="m13 7 5 5-5 5M6 7l5 5-5 5" />
              ) : (
                <path d="m11 7-5 5 5 5M18 7l-5 5 5 5" />
              )}
            </svg>
          </button>
        )}
      </div>

      {!collapsed && (
        <nav className="min-h-0 flex-1 overflow-y-auto px-2.5 py-3">
          {groups.map((group) => (
            <div key={group.title} className="mb-4 last:mb-0">
              <div className="eyebrow px-2 pb-1.5">{group.title}</div>
              <ul className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/'}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cx(
                          'flex items-center justify-between gap-2 rounded px-2 py-1.5 text-[13px] transition-colors',
                          isActive
                            ? 'bg-accent-soft font-medium text-ink'
                            : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span className="flex min-w-0 items-center gap-2">
                            <span
                              className={cx(
                                'h-3.5 w-[2px] shrink-0 rounded-full',
                                isActive ? 'bg-accent' : 'bg-transparent',
                              )}
                            />
                            <span className="truncate">{item.label}</span>
                          </span>
                          {item.badge ? (
                            <span className="tabular shrink-0 rounded bg-critical/18 px-1.5 py-px text-[10px] font-semibold text-critical">
                              {item.badge}
                            </span>
                          ) : null}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      )}
    </aside>
  );
}

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#15304d" />
      <path d="M16 7c-4.8 0-8.6 3.5-8.6 8.2V20h17.2v-4.8C24.6 10.5 20.8 7 16 7z" fill="#3987e5" />
      <rect x="5.6" y="20.2" width="20.8" height="3.4" rx="1.7" fill="#9aa8bd" />
      <path d="M13.2 10.4v8.2M18.8 10.4v8.2" stroke="#15304d" strokeWidth="1.3" />
    </svg>
  );
}
