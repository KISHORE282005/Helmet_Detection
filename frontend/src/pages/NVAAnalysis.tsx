/** Non-Value-Added activity analysis.
 *
 *  Three questions, in the order a supervisor asks them: where did operator
 *  time actually go, which of it added no value, and what should change first.
 *  Every figure is measured time — the page shows an em dash rather than a
 *  zero when nothing has been analysed, because an empty plant has no
 *  value-added ratio.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { BarList, TrendChart } from '../components/charts/charts';
import { NoDataValue, StatTile } from '../components/domain/StatTile';
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Panel,
  Skeleton,
  cx,
  type Tone,
} from '../components/ui/primitives';
import { useNva, useNvaActivities, useNvaCatalog } from '../lib/hooks';
import { labelDay, percent, shortDate } from '../lib/format';
import type {
  NvaGroupRow,
  NvaRecommendation,
  NvaSummary,
  ValueClass,
} from '../lib/types';

const RANGES = [
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: '90d', label: 'Last 90 days' },
];

const CLASS_TONE: Record<ValueClass, Tone> = {
  VA: 'good',
  NNVA: 'warning',
  NVA: 'critical',
};

const SEVERITY_TONE: Record<NvaRecommendation['severity'], Tone> = {
  high: 'critical',
  medium: 'warning',
  low: 'neutral',
};

export default function NVAAnalysis() {
  const [range, setRange] = useState('7d');
  const { data, isLoading, isError, error, refetch } = useNva({ range });
  const catalog = useNvaCatalog();
  const segments = useNvaActivities({ range, value_class: 'NVA', limit: 12 });

  if (isError) {
    return (
      <>
        <PageHeader title="NVA Analysis" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const target = data?.thresholds.target_va_ratio ?? 60;
  const hasData = (data?.classified_seconds ?? 0) > 0;
  const worstWaste = data?.by_waste?.[0];

  return (
    <>
      <PageHeader
        title="NVA Analysis"
        subtitle={
          data
            ? `Value stream · ${shortDate(data.range.from)} — ${shortDate(data.range.to)}`
            : 'Where operator time goes, and what to change first'
        }
        actions={
          <div className="flex rounded border border-line-strong bg-surface-2 p-0.5">
            {RANGES.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setRange(option.key)}
                className={cx(
                  'rounded px-2.5 py-1 text-[11px] font-medium transition-colors',
                  range === option.key ? 'bg-accent text-white' : 'text-ink-2 hover:text-ink',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        }
      />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Value-Added Ratio"
          loading={isLoading}
          value={data?.va_ratio === null || data?.va_ratio === undefined
            ? <NoDataValue />
            : percent(data.va_ratio)}
          tone={
            data?.va_ratio === null || data?.va_ratio === undefined
              ? 'neutral'
              : data.va_ratio >= target
                ? 'good'
                : data.va_ratio >= target * 0.7
                  ? 'warning'
                  : 'critical'
          }
          footnote={`target ${target.toFixed(0)}% of classified time`}
        />
        <StatTile
          label="Non-Value-Added Time"
          loading={isLoading}
          value={hasData ? (data?.value_split.find((r) => r.value_class === 'NVA')?.duration ?? '—') : <NoDataValue />}
          tone={hasData ? 'critical' : 'neutral'}
          footnote={
            data?.nva_ratio !== null && data?.nva_ratio !== undefined
              ? `${percent(data.nva_ratio)} of classified time`
              : 'no footage analysed'
          }
        />
        <StatTile
          label="Largest Waste"
          loading={isLoading}
          value={worstWaste ? worstWaste.waste : <NoDataValue />}
          tone={worstWaste ? 'serious' : 'neutral'}
          footnote={
            worstWaste
              ? `${worstWaste.duration} across ${worstWaste.occurrences} occurrence${worstWaste.occurrences === 1 ? '' : 's'}`
              : 'nothing charged to waste yet'
          }
        />
        <StatTile
          label="Operator Time Observed"
          loading={isLoading}
          value={data?.observed_seconds ? data.observed_duration : <NoDataValue />}
          footnote={
            data?.tracks
              ? `${data.tracks.toLocaleString('en-US')} people · ${data.classified_duration} classified`
              : 'no people tracked'
          }
        />
      </div>

      {!isLoading && !hasData ? (
        <Panel>
          <EmptyState
            title="No activity analysed for this period"
            description="NVA figures come from the same analysis runs as safety incidents. Analyse a recording or start a live camera, then come back."
            action={
              <Link to="/analysis">
                <Button size="sm" variant="primary">
                  Analyse footage
                </Button>
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Panel
            eyebrow="Value stream"
            title="Where Operator Time Went"
            className="xl:col-span-2"
          >
            {isLoading ? <Skeleton className="h-24 w-full" /> : <ValueSplit data={data} />}
          </Panel>

         

          

          <Panel eyebrow="Over time" title="NVA Trend">
            {isLoading ? (
              <Skeleton className="h-[180px] w-full" />
            ) : (
              <>
                <TrendChart
                  height={180}
                  points={(data?.trend ?? []).map((point) => ({
                    date: point.date,
                    count: point.count,
                    label: labelDay(point.date),
                  }))}
                />
                <p className="mt-2 text-[10px] text-ink-3">
                  Minutes of non-value-added operator time per day.
                </p>
              </>
            )}
          </Panel>

          <Panel
            eyebrow="Improvement plan"
            title="Recommended Actions"
            className="xl:col-span-3"
          >
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (data?.recommendations.length ?? 0) === 0 ? (
              <EmptyState
                compact
                title="No waste crossed the reporting threshold"
                description={`Nothing accounted for more than ${data?.thresholds.recommend_min_share ?? 2}% of classified time, so there is no action worth raising.`}
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                {data?.recommendations.map((action) => (
                  <RecommendationCard key={action.id} action={action} />
                ))}
              </div>
            )}
          </Panel>

          

          


          <Panel
            eyebrow="Reference"
            title="Which Activities Count as NVA"
            dense
            className="xl:col-span-3"
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left">
                <thead>
                  <tr className="border-b border-line text-[10px] tracking-wider text-ink-3 uppercase">
                    <th className="px-3 py-2">Activity</th>
                    <th className="px-3 py-2">Classification</th>
                    <th className="px-3 py-2">Lean waste</th>
                    <th className="px-3 py-2">What it means</th>
                    <th className="px-3 py-2">How it is detected</th>
                  </tr>
                </thead>
                <tbody>
                  {(catalog.data?.activities ?? [])
                    .filter((entry) => entry.value_class !== null)
                    .map((entry) => (
                      <tr key={entry.key} className="border-b border-line align-top last:border-0">
                        <td className="px-3 py-2 text-xs font-medium text-ink">{entry.label}</td>
                        <td className="px-3 py-2">
                          <Badge tone={CLASS_TONE[entry.value_class as ValueClass]}>
                            {entry.value_class}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-xs text-ink-2">{entry.waste ?? '—'}</td>
                        <td className="max-w-[280px] px-3 py-2 text-[11px] leading-relaxed text-ink-2">
                          {entry.description}
                        </td>
                        <td className="max-w-[280px] px-3 py-2 text-[11px] leading-relaxed text-ink-3">
                          {entry.detection}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-line px-3 py-2.5 text-[10px] leading-relaxed text-ink-3">
              Value-Added is work the customer pays for. Necessary NVA has to happen in
              today's process but adds nothing — minimise it. Non-Value-Added is pure
              waste. Shares are taken over classified time only: a person whose activity
              could not be determined is left out of both sides rather than counted as
              value.
            </p>
          </Panel>
        </div>
      )}
    </>
  );
}

/** The single most important chart on the page: one bar, three segments. */
function ValueSplit({ data }: { data?: NvaSummary }) {
  const rows = data?.value_split ?? [];
  const total = rows.reduce((sum, row) => sum + row.seconds, 0);
  if (total <= 0) return <EmptyState compact title="Nothing classified yet" />;

  return (
    <>
      <div className="flex h-9 w-full overflow-hidden rounded border border-line-strong">
        {rows
          .filter((row) => row.seconds > 0)
          .map((row) => (
            <div
              key={row.value_class}
              title={`${row.label}: ${row.duration} (${row.share}%)`}
              style={{ width: `${(row.seconds / total) * 100}%` }}
              className={cx(
                'flex items-center justify-center text-[10px] font-semibold text-white',
                row.value_class === 'VA' && 'bg-good',
                row.value_class === 'NNVA' && 'bg-warning',
                row.value_class === 'NVA' && 'bg-critical',
              )}
            >
              {row.share >= 8 ? `${row.share}%` : ''}
            </div>
          ))}
      </div>
      <ul className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        {rows.map((row) => (
          <li key={row.value_class} className="rounded border border-line bg-surface-2 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <Badge tone={CLASS_TONE[row.value_class]}>{row.value_class}</Badge>
              <span className="tabular text-[13px] font-semibold text-ink">{row.duration}</span>
            </div>
            <div className="mt-1 text-[11px] font-medium text-ink">{row.label}</div>
            <p className="mt-0.5 text-[10px] leading-relaxed text-ink-3">{row.description}</p>
          </li>
        ))}
      </ul>
    </>
  );
}

function RecommendationCard({ action }: { action: NvaRecommendation }) {
  return (
    <article className="flex flex-col rounded border border-line bg-surface-2 p-3.5">
      <header className="mb-2 flex items-start justify-between gap-2">
        <h3 className="text-[13px] leading-snug font-semibold text-ink">{action.title}</h3>
        <div className="flex shrink-0 items-center gap-1.5">
          {action.waste && <Badge tone="neutral">{action.waste}</Badge>}
          <Badge tone={SEVERITY_TONE[action.severity]}>{action.severity}</Badge>
        </div>
      </header>

      <p className="text-[11px] leading-relaxed text-ink-2">{action.observation}</p>

      {action.root_causes.length > 0 && (
        <>
          <div className="eyebrow mt-3 mb-1">Likely causes</div>
          <ul className="flex flex-col gap-0.5">
            {action.root_causes.map((cause) => (
              <li key={cause} className="flex gap-1.5 text-[11px] leading-relaxed text-ink-3">
                <span className="text-ink-3">·</span>
                <span>{cause}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="eyebrow mt-3 mb-1">Do this</div>
      <ol className="flex flex-col gap-1">
        {action.actions.map((step, index) => (
          <li key={step} className="flex gap-2 text-[11px] leading-relaxed text-ink-2">
            <span className="tabular shrink-0 font-semibold text-accent">{index + 1}.</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>

      <footer className="mt-3 border-t border-line pt-2.5 text-[10px] leading-relaxed text-ink-3">
        <div>
          <span className="font-semibold text-ink-2">Lean tool:</span> {action.lean_tool}
        </div>
        <div className="mt-0.5">
          <span className="font-semibold text-ink-2">Impact:</span> {action.expected_impact}
        </div>
        <div className="mt-0.5">
          <span className="font-semibold text-ink-2">Verify:</span> {action.verify}
        </div>
      </footer>
    </article>
  );
}

function GroupList({ rows, empty }: { rows: NvaGroupRow[]; empty: string }) {
  if (rows.length === 0) return <EmptyState compact title={empty} />;
  return (
    <BarList
      unit="NVA minutes"
      data={rows.map((row) => ({
        key: row.key || 'unassigned',
        label: row.key || 'Unassigned',
        count: row.count,
        meta: `${row.duration} NVA · ${percent(row.nva_share)} of its tracked time`,
      }))}
    />
  );
}
