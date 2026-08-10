/** KPI tile. Contract: label, value, optional delta against a named period,
 *  optional sparkline. The value is the only loud thing in the tile. */

import type { ReactNode } from 'react';
import { Sparkline } from '../charts/charts';
import { StatusDot, cx, type Tone } from '../ui/primitives';
import { DASH, signedPercent } from '../../lib/format';

export function StatTile({
  label,
  value,
  unit,
  tone = 'neutral',
  footnote,
  delta,
  deltaLabel,
  /** Whether a rising number is good news. Compliance up = good; violations up = bad. */
  upIsGood = false,
  trend,
  status,
  loading,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: Tone;
  footnote?: ReactNode;
  delta?: number | null;
  deltaLabel?: string;
  upIsGood?: boolean;
  trend?: number[];
  status?: { tone: Tone; label: string };
  loading?: boolean;
}) {
  const deltaTone: Tone =
    delta === null || delta === undefined || delta === 0
      ? 'neutral'
      : delta > 0 === upIsGood
        ? 'good'
        : 'critical';

  return (
    <div
      className={cx(
        'relative flex min-w-0 flex-col justify-between overflow-hidden rounded-lg border bg-surface p-4',
        tone === 'critical' ? 'border-critical/40' : 'border-line',
      )}
    >
      {/* A thin accent rail is the only decoration; it encodes severity. */}
      {tone !== 'neutral' && (
        <span
          className={cx(
            'absolute inset-y-0 left-0 w-[3px]',
            tone === 'good' && 'bg-good',
            tone === 'warning' && 'bg-warning',
            tone === 'serious' && 'bg-serious',
            tone === 'critical' && 'bg-critical',
            tone === 'accent' && 'bg-accent',
          )}
        />
      )}

      <div className="flex items-start justify-between gap-2">
        <span className="eyebrow">{label}</span>
        {status && <StatusDot tone={status.tone} label={<span className="text-[10px] text-ink-3">{status.label}</span>} size="sm" />}
      </div>

      <div className="mt-2 flex items-end gap-2">
        {loading ? (
          <div className="h-8 w-20 animate-pulse rounded bg-surface-2" />
        ) : (
          <>
            <span
              className={cx(
                'text-[30px] leading-none font-semibold tracking-tight',
                tone === 'critical' ? 'text-critical' : 'text-ink',
              )}
            >
              {value}
            </span>
            {unit && <span className="pb-1 text-xs text-ink-3">{unit}</span>}
          </>
        )}
        {trend && trend.length > 1 && (
          <div className="ml-auto pb-0.5">
            <Sparkline values={trend} />
          </div>
        )}
      </div>

      <div className="mt-2 flex min-h-4 flex-wrap items-center gap-x-2 gap-y-1">
        {delta !== undefined && (
          <span
            className={cx(
              'inline-flex items-center gap-1 text-[11px] font-medium',
              deltaTone === 'good' && 'text-good',
              deltaTone === 'critical' && 'text-critical',
              deltaTone === 'neutral' && 'text-ink-3',
            )}
          >
            {delta !== null && delta !== 0 && (
              <ArrowIcon up={delta > 0} className="h-3 w-3" />
            )}
            {delta === null ? 'no baseline' : signedPercent(delta)}
            {deltaLabel && <span className="font-normal text-ink-3">{deltaLabel}</span>}
          </span>
        )}
        {footnote && <span className="text-[11px] text-ink-3">{footnote}</span>}
      </div>
    </div>
  );
}

/** Used when a metric genuinely has no data yet, so it never shows a fake 0%. */
export function NoDataValue() {
  return <span className="text-[30px] leading-none font-semibold text-ink-3">{DASH}</span>;
}

function ArrowIcon({ up, className }: { up: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 12 12" className={className} aria-hidden="true" fill="currentColor">
      {up ? <path d="M6 2.5 10 8H2z" /> : <path d="M6 9.5 2 4h8z" />}
    </svg>
  );
}
