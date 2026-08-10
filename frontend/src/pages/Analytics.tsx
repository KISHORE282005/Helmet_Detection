/** Manufacturing safety analytics over a selectable window. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import {
  BarList,
  ColumnChart,
  SuppressionMeter,
  TrendChart,
} from '../components/charts/charts';
import { StatTile, NoDataValue } from '../components/domain/StatTile';
import {
  Button,
  EmptyState,
  ErrorState,
  Panel,
  Skeleton,
  cx,
} from '../components/ui/primitives';
import { useAnalytics } from '../lib/hooks';
import { confidencePercent, labelDay, percent, shortDate } from '../lib/format';

const RANGES = [
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: '90d', label: 'Last 90 days' },
];

export default function Analytics() {
  const [range, setRange] = useState('7d');
  const { data, isLoading, isError, error, refetch } = useAnalytics(range);

  if (isError) {
    return (
      <>
        <PageHeader title="Analytics" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const totals = data?.totals;
  const hasData = (totals?.incidents ?? 0) > 0 || (totals?.runs ?? 0) > 0;

  return (
    <>
      <PageHeader
        title="Safety Analytics"
        subtitle={
          data
            ? `${shortDate(data.range.from)} — ${shortDate(data.range.to)}`
            : 'Violation patterns across cameras, locations and time'
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
                  range === option.key
                    ? 'bg-accent text-white'
                    : 'text-ink-2 hover:text-ink',
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
          label="Total Violations"
          loading={isLoading}
          value={totals?.incidents ?? 0}
          tone={totals?.incidents ? 'critical' : 'neutral'}
          footnote="unique incidents"
        />
        <StatTile
          label="Compliance Rate"
          loading={isLoading}
          value={
            totals?.compliance_rate === null || totals?.compliance_rate === undefined ? (
              <NoDataValue />
            ) : (
              percent(totals.compliance_rate)
            )
          }
          tone={
            totals?.compliance_rate === null || totals?.compliance_rate === undefined
              ? 'neutral'
              : totals.compliance_rate >= 95
                ? 'good'
                : totals.compliance_rate >= 85
                  ? 'warning'
                  : 'critical'
          }
          footnote={
            totals?.people_detected
              ? `${totals.people_detected.toLocaleString('en-US')} people tracked`
              : 'no footage analysed'
          }
        />
        <StatTile
          label="Duplicates Suppressed"
          loading={isLoading}
          value={(totals?.suppressed_duplicates ?? 0).toLocaleString('en-US')}
          tone="accent"
          footnote="repeat detections collapsed by track"
        />
        <StatTile
          label="Average Confidence"
          loading={isLoading}
          value={totals ? confidencePercent(totals.avg_confidence) : <NoDataValue />}
          footnote={`${(totals?.frames_analyzed ?? 0).toLocaleString('en-US')} frames analysed`}
        />
      </div>

      {!isLoading && !hasData ? (
        <Panel>
          <EmptyState
            title="No analytics for this period"
            description="Analytics are computed from completed analysis runs. Analyse a recording, or widen the date range."
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
          <Panel eyebrow="Over time" title="Violation Trend" className="xl:col-span-2">
            {isLoading ? (
              <Skeleton className="h-[200px] w-full" />
            ) : (
              <TrendChart
                height={200}
                points={(data?.trend ?? []).map((point) => ({
                  date: point.date,
                  count: point.count,
                  label: labelDay(point.date),
                }))}
              />
            )}
          </Panel>

          <Panel eyebrow="Pipeline" title="Detections vs Incidents">
            {isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <>
                <SuppressionMeter
                  raw={totals?.raw_detections ?? 0}
                  unique={totals?.incidents ?? 0}
                />
                <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-ink-3">
                  Every helmet-missing frame counts as a raw detection. Incidents count
                  tracked people. A wide gap means the tracker is doing its job.
                </p>
              </>
            )}
          </Panel>

          <Panel eyebrow="By camera" title="Camera Performance">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (data?.by_camera.length ?? 0) === 0 ? (
              <EmptyState compact title="No incidents attributed to a camera" />
            ) : (
              <BarList
                data={(data?.by_camera ?? []).map((row) => ({
                  key: row.key || 'unassigned',
                  label: row.key || 'Unassigned',
                  count: row.count,
                  meta: row.avg_confidence
                    ? `avg confidence ${confidencePercent(row.avg_confidence)}`
                    : undefined,
                }))}
              />
            )}
          </Panel>

          <Panel eyebrow="By area" title="Location Performance">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (data?.by_location.length ?? 0) === 0 ? (
              <EmptyState compact title="No incidents attributed to a location" />
            ) : (
              <BarList
                data={(data?.by_location ?? []).map((row) => ({
                  key: row.key || 'unassigned',
                  label: row.key || 'Unassigned',
                  count: row.count,
                }))}
              />
            )}
          </Panel>

          <Panel eyebrow="By hour of footage" title="When Violations Happen">
            {isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (data?.by_hour.length ?? 0) === 0 ? (
              <EmptyState compact title="Not enough data to show a distribution" />
            ) : (
              <>
                <ColumnChart
                  data={buildHours(data?.by_hour ?? [])}
                  height={120}
                />
                <p className="mt-2 text-[10px] text-ink-3">
                  Hour of the source recording's own clock, not the analysis time.
                </p>
              </>
            )}
          </Panel>

          <Panel
            eyebrow="Runs"
            title="Recent Analysis Runs"
            dense
            className="xl:col-span-3"
          >
            {(data?.recent_runs.length ?? 0) === 0 ? (
              <EmptyState compact title="No completed analysis runs in this period" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left">
                  <thead>
                    <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-3">
                      <th className="px-3 py-2">Source</th>
                      <th className="px-3 py-2">Camera</th>
                      <th className="px-3 py-2">Finished</th>
                      <th className="px-3 py-2 text-right">Frames</th>
                      <th className="px-3 py-2 text-right">People</th>
                      <th className="px-3 py-2 text-right">Raw detections</th>
                      <th className="px-3 py-2 text-right">Incidents</th>
                      <th className="px-3 py-2 text-right">Processing FPS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data?.recent_runs.map((run) => (
                      <tr key={run.run_id} className="border-b border-line last:border-0">
                        <td className="max-w-[220px] truncate px-3 py-2 text-xs text-ink">
                          {run.video_name}
                        </td>
                        <td className="px-3 py-2 text-xs text-ink-2">
                          {run.camera_id || '—'}
                        </td>
                        <td className="tabular px-3 py-2 text-xs text-ink-2">
                          {shortDate(run.finished_at)}
                        </td>
                        <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                          {run.frames_analyzed.toLocaleString('en-US')}
                        </td>
                        <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                          {run.people_detected}
                        </td>
                        <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                          {run.raw_detections}
                        </td>
                        <td className="tabular px-3 py-2 text-right text-xs font-semibold text-critical">
                          {run.unique_incidents}
                        </td>
                        <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                          {run.processing_fps.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      )}
    </>
  );
}

/** Fill all 24 hours so the distribution isn't misread as a dense cluster. */
function buildHours(rows: { key: string; count: number }[]) {
  const counts = new Map(rows.map((row) => [row.key.padStart(2, '0'), row.count]));
  return Array.from({ length: 24 }, (_, hour) => {
    const key = String(hour).padStart(2, '0');
    return { key, label: key, count: counts.get(key) ?? 0 };
  });
}
