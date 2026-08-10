/** Daily / weekly / monthly safety reports with Excel, CSV and PDF export. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { BarList, TrendChart } from '../components/charts/charts';
import {
  Badge,
  Button,
  DownloadIcon,
  EmptyState,
  ErrorState,
  LinkButton,
  Modal,
  Panel,
  Skeleton,
  StatusBadge,
  cx,
} from '../components/ui/primitives';
import { reportExportUrl } from '../lib/api';
import { useReport, useReportSummary } from '../lib/hooks';
import {
  confidencePercent,
  labelDay,
  percent,
  shortDate,
} from '../lib/format';
import type { SafetyReport } from '../lib/types';

const PERIOD_TITLE: Record<string, string> = {
  daily: 'Daily Report',
  weekly: 'Weekly Report',
  monthly: 'Monthly Report',
};

export default function Reports() {
  const { data, isLoading, isError, error, refetch } = useReportSummary();
  const [open, setOpen] = useState<string | null>(null);

  if (isError) {
    return (
      <>
        <PageHeader title="Safety Reports" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Safety Reports"
        subtitle="PPE compliance summaries for the safety and EHS record"
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-72 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {data?.reports.map((report) => (
            <ReportCard
              key={report.period}
              report={report}
              onView={() => setOpen(report.period)}
            />
          ))}
        </div>
      )}

      <ReportModal period={open} onClose={() => setOpen(null)} />
    </>
  );
}

function ReportCard({ report, onView }: { report: SafetyReport; onView: () => void }) {
  const { totals } = report;

  return (
    <Panel eyebrow={PERIOD_TITLE[report.period]} title={report.label}>
      {!report.has_data ? (
        <EmptyState
          compact
          title="No data for this period"
          description="Reports populate once footage has been analysed in the selected window."
          action={
            <Link to="/analysis">
              <Button size="sm" variant="primary">
                Analyse footage
              </Button>
            </Link>
          }
        />
      ) : (
        <>
          <div className="flex items-end gap-4">
            <div>
              <div className="eyebrow">Violations</div>
              <div
                className={cx(
                  'text-3xl leading-none font-semibold',
                  totals.violations > 0 ? 'text-critical' : 'text-ink',
                )}
              >
                {totals.violations}
              </div>
            </div>
            <div>
              <div className="eyebrow">Compliance</div>
              <div className="text-3xl leading-none font-semibold text-ink">
                {totals.compliance_rate === null ? '—' : percent(totals.compliance_rate)}
              </div>
            </div>
          </div>

          <dl className="mt-4 flex flex-col divide-y divide-line border-y border-line">
            <Row label="Raw detections" value={totals.raw_detections.toLocaleString('en-US')} />
            <Row label="People tracked" value={totals.people_detected.toLocaleString('en-US')} />
            <Row label="Analysis runs" value={String(totals.analysis_runs)} />
            <Row
              label="Average confidence"
              value={confidencePercent(totals.avg_confidence)}
            />
            <Row
              label="Most affected camera"
              value={report.worst_camera ? `${report.worst_camera.key} (${report.worst_camera.count})` : '—'}
            />
            <Row
              label="Most affected location"
              value={
                report.worst_location
                  ? `${report.worst_location.key} (${report.worst_location.count})`
                  : '—'
              }
            />
          </dl>

          {report.period !== 'daily' && report.trend.length > 1 && (
            <div className="mt-3">
              <div className="eyebrow mb-1">Daily violations</div>
              <TrendChart
                height={110}
                points={report.trend.map((point) => ({
                  date: point.key,
                  count: point.count,
                  label: labelDay(point.key),
                }))}
              />
            </div>
          )}
        </>
      )}

      <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-3">
        <Button variant="primary" size="sm" onClick={onView} disabled={!report.has_data}>
          View report
        </Button>
        <LinkButton href={reportExportUrl(report.period, 'xlsx')} size="sm" download>
          <DownloadIcon className="h-3.5 w-3.5" />
          Excel
        </LinkButton>
        <LinkButton href={reportExportUrl(report.period, 'pdf')} size="sm" download>
          <DownloadIcon className="h-3.5 w-3.5" />
          PDF
        </LinkButton>
        <LinkButton href={reportExportUrl(report.period, 'csv')} size="sm" download>
          CSV
        </LinkButton>
      </div>
    </Panel>
  );
}

function ReportModal({ period, onClose }: { period: string | null; onClose: () => void }) {
  const { data, isLoading } = useReport(period ?? 'daily', Boolean(period));

  return (
    <Modal
      open={Boolean(period)}
      onClose={onClose}
      title={period ? PERIOD_TITLE[period] : ''}
      subtitle={data?.label}
      width="max-w-6xl"
    >
      {isLoading || !data ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Stat label="Unique incidents" value={String(data.totals.violations)} tone="critical" />
            <Stat label="Raw detections" value={data.totals.raw_detections.toLocaleString('en-US')} />
            <Stat label="People tracked" value={data.totals.people_detected.toLocaleString('en-US')} />
            <Stat
              label="Compliance"
              value={data.totals.compliance_rate === null ? '—' : percent(data.totals.compliance_rate)}
              tone="good"
            />
            <Stat label="Analysis runs" value={String(data.totals.analysis_runs)} />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel eyebrow="Breakdown" title="Violations by camera">
              {data.by_camera.length === 0 ? (
                <EmptyState compact title="No incidents in this period" />
              ) : (
                <BarList
                  data={data.by_camera.map((row) => ({
                    key: row.key || 'unassigned',
                    label: row.key || 'Unassigned',
                    count: row.count,
                  }))}
                />
              )}
            </Panel>
            <Panel eyebrow="Breakdown" title="Violations by location">
              {data.by_location.length === 0 ? (
                <EmptyState compact title="No incidents in this period" />
              ) : (
                <BarList
                  data={data.by_location.map((row) => ({
                    key: row.key || 'unassigned',
                    label: row.key || 'Unassigned',
                    count: row.count,
                  }))}
                />
              )}
            </Panel>
          </div>

          <Panel eyebrow="Detail" title={`Incidents (${data.incidents?.length ?? 0})`} dense>
            {(data.incidents?.length ?? 0) === 0 ? (
              <EmptyState compact title="No incidents recorded in this period" />
            ) : (
              <div className="max-h-80 overflow-auto">
                <table className="w-full min-w-[720px] text-left">
                  <thead className="sticky top-0 bg-surface">
                    <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-3">
                      <th className="px-3 py-2">Incident</th>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2">Video time</th>
                      <th className="px-3 py-2">Camera</th>
                      <th className="px-3 py-2">Location</th>
                      <th className="px-3 py-2 text-right">Confidence</th>
                      <th className="px-3 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.incidents?.map((incident) => (
                      <tr key={incident.incident_id} className="border-b border-line last:border-0">
                        <td className="px-3 py-1.5">
                          <Link
                            to={`/incidents/${incident.incident_id}`}
                            onClick={onClose}
                            className="tabular text-xs text-accent hover:underline"
                          >
                            {incident.incident_id}
                          </Link>
                        </td>
                        <td className="tabular px-3 py-1.5 text-xs text-ink-2">
                          {shortDate(incident.date)}
                        </td>
                        <td className="tabular px-3 py-1.5 text-xs text-ink-2">
                          {incident.video_time}
                        </td>
                        <td className="px-3 py-1.5 text-xs text-ink-2">{incident.camera_id}</td>
                        <td className="max-w-[160px] truncate px-3 py-1.5 text-xs text-ink-2">
                          {incident.location || '—'}
                        </td>
                        <td className="tabular px-3 py-1.5 text-right text-xs text-ink">
                          {confidencePercent(incident.confidence)}
                        </td>
                        <td className="px-3 py-1.5">
                          <StatusBadge status={incident.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <Badge tone="neutral">
              {data.range.from} to {data.range.to}
            </Badge>
            <div className="ml-auto flex gap-2">
              <LinkButton href={reportExportUrl(data.period, 'xlsx')} size="sm" download>
                <DownloadIcon className="h-3.5 w-3.5" />
                Export Excel
              </LinkButton>
              <LinkButton href={reportExportUrl(data.period, 'pdf')} size="sm" download>
                <DownloadIcon className="h-3.5 w-3.5" />
                Export PDF
              </LinkButton>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="text-[11px] text-ink-3">{label}</dt>
      <dd className="tabular truncate text-xs font-medium text-ink">{value}</dd>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'critical' | 'good';
}) {
  return (
    <div className="rounded border border-line bg-surface-2 p-2.5">
      <div className="eyebrow truncate">{label}</div>
      <div
        className={cx(
          'tabular mt-1 text-lg font-semibold',
          tone === 'critical' && 'text-critical',
          tone === 'good' && 'text-good',
          !tone && 'text-ink',
        )}
      >
        {value}
      </div>
    </div>
  );
}
