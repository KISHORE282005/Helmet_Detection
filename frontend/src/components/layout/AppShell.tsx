/** Fixed sidebar + header frame. Only the content column scrolls, so the
 *  header and system status stay visible on a wall-mounted monitor. */

import { type ReactNode, useState } from 'react';
import { useDashboard } from '../../lib/hooks';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { cx } from '../ui/primitives';

export function AppShell({ children }: { children: ReactNode }) {
  const dashboard = useDashboard();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-full w-full overflow-hidden bg-plane">
      <Sidebar
        openViolations={dashboard.data?.active_violations.count ?? 0}
        className="flex"
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((collapsed) => !collapsed)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1800px] p-4 lg:p-5">{children}</div>
        </main>
      </div>
    </div>
  );
}

/** Standard page heading. `actions` sits on the right at every breakpoint. */
export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        'mb-4 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-3',
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
