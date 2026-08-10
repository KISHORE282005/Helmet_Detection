/** Incident presentation shared by the dashboard, violations queue and gallery. */

import { Link } from 'react-router-dom';
import { mediaUrl } from '../../lib/api';
import { confidencePercent, relativeTime, shortDate } from '../../lib/format';
import type { Incident } from '../../lib/types';
import {
  AlertIcon,
  Badge,
  Button,
  ImageIcon,
  StatusBadge,
  cx,
} from '../ui/primitives';

export function EvidenceThumb({
  incident,
  className,
  alt,
}: {
  incident: Incident;
  className?: string;
  alt?: string;
}) {
  if (!incident.evidence) {
    return (
      <div
        className={cx(
          'flex items-center justify-center rounded border border-line bg-surface-2 text-ink-3',
          className,
        )}
        title="The evidence image for this incident is no longer on disk"
      >
        <ImageIcon className="h-5 w-5" />
      </div>
    );
  }
  return (
    <img
      src={mediaUrl('evidence', incident.evidence)}
      alt={alt ?? `Evidence for ${incident.incident_id}`}
      loading="lazy"
      className={cx('rounded border border-line bg-plane object-cover', className)}
    />
  );
}

/** Compact row for the "needs attention" queue. */
export function IncidentRow({ incident }: { incident: Incident }) {
  return (
    <Link
      to={`/incidents/${incident.incident_id}`}
      className="flex gap-3 border-b border-line px-3 py-2.5 transition-colors last:border-b-0 hover:bg-surface-2"
    >
      <EvidenceThumb incident={incident} className="h-14 w-20 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="tabular text-xs font-semibold text-ink">
            {incident.incident_id}
          </span>
          <Badge tone="critical" icon={<AlertIcon className="h-2.5 w-2.5" />}>
            {incident.violation_type}
          </Badge>
          <StatusBadge status={incident.status} />
        </div>
        <p className="mt-1 truncate text-[11px] text-ink-2">
          {incident.camera_id} · {incident.location || incident.camera_name}
        </p>
        <p className="tabular mt-0.5 text-[10px] text-ink-3">
          Video {incident.video_time} · Track #{incident.track_id} ·{' '}
          {confidencePercent(incident.confidence)} confidence ·{' '}
          {relativeTime(incident.detected_at)}
        </p>
      </div>
    </Link>
  );
}

/** Card used in the Active Violations grid. */
export function IncidentCard({ incident }: { incident: Incident }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-lg border border-critical/35 bg-surface">
      <div className="relative aspect-video w-full bg-plane">
        <EvidenceThumb
          incident={incident}
          className="h-full w-full rounded-none border-0"
        />
        <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 bg-gradient-to-b from-black/80 to-transparent p-2">
          <Badge tone="critical" icon={<AlertIcon className="h-2.5 w-2.5" />}>
            {incident.violation_type}
          </Badge>
          <span className="tabular rounded bg-black/65 px-1.5 py-0.5 text-[10px] font-medium text-ink">
            {confidencePercent(incident.confidence)}
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="tabular text-[13px] font-semibold text-ink">
            {incident.incident_id}
          </span>
          <StatusBadge status={incident.status} />
        </div>

        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
          <Detail label="Camera" value={incident.camera_id} />
          <Detail label="Video time" value={incident.video_time} />
          <Detail
            label="Location"
            value={incident.location || incident.camera_name || '—'}
            className="col-span-2"
          />
          <Detail label="Track" value={`#${incident.track_id}`} />
          <Detail label="Recorded" value={shortDate(incident.detected_at)} />
        </dl>

        <Link to={`/incidents/${incident.incident_id}`} className="mt-auto pt-1">
          <Button variant="primary" size="sm" className="w-full">
            Review incident
          </Button>
        </Link>
      </div>
    </article>
  );
}

function Detail({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={cx('min-w-0', className)}>
      <dt className="truncate text-ink-3">{label}</dt>
      <dd className="tabular truncate font-medium text-ink" title={value}>
        {value}
      </dd>
    </div>
  );
}

/**
 * The detection -> violation -> incident -> evidence hierarchy, stated on the
 * incident itself. It is the clearest place to show that 500 frames of one
 * person produce exactly one record.
 */
export function DetectionHierarchy({ incident }: { incident: Incident }) {
  const steps = [
    {
      key: 'detection',
      title: 'Detection',
      value: `${incident.scene_persons} person${incident.scene_persons === 1 ? '' : 's'} in frame`,
      detail: `${incident.scene_helmet} with helmet · ${incident.scene_no_helmet} without`,
      tone: 'accent' as const,
    },
    {
      key: 'violation',
      title: 'Violation',
      value: `Track #${incident.track_id} without helmet`,
      detail: incident.confirm_frames
        ? `Held for ${incident.confirm_frames} consecutive frames`
        : 'Confirmed by temporal verification',
      tone: 'critical' as const,
    },
    {
      key: 'incident',
      title: 'Incident',
      value: incident.incident_id,
      detail: 'One record per tracked person — repeats are suppressed',
      tone: 'serious' as const,
    },
    {
      key: 'evidence',
      title: 'Evidence',
      value: incident.evidence ? 'Best frame saved' : 'Image unavailable',
      detail: incident.evidence
        ? 'Chosen by size, sharpness and confidence'
        : 'The file is no longer in output/images',
      tone: incident.evidence ? ('good' as const) : ('neutral' as const),
    },
  ];

  return (
    <ol className="flex flex-col gap-0">
      {steps.map((step, index) => (
        <li key={step.key} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span
              className={cx(
                'mt-1 h-2 w-2 shrink-0 rounded-full',
                step.tone === 'accent' && 'bg-accent',
                step.tone === 'critical' && 'bg-critical',
                step.tone === 'serious' && 'bg-serious',
                step.tone === 'good' && 'bg-good',
                step.tone === 'neutral' && 'bg-ink-3',
              )}
            />
            {index < steps.length - 1 && <span className="w-px flex-1 bg-line-strong" />}
          </div>
          <div className={cx('min-w-0 flex-1', index < steps.length - 1 && 'pb-3')}>
            <div className="eyebrow">{step.title}</div>
            <p className="truncate text-xs font-medium text-ink">{step.value}</p>
            <p className="text-[10px] leading-relaxed text-ink-3">{step.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/** Explains the colours burned into the evidence frame by the detector. */
export function DetectionLegend() {
  const entries = [
    { color: '#22c55e', label: 'Helmet detected' },
    { color: '#ef4444', label: 'Helmet missing' },
    { color: '#9ca3af', label: 'Head not assessable' },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {entries.map((entry) => (
        <span key={entry.label} className="flex items-center gap-1.5 text-[10px] text-ink-3">
          <span
            className="h-2.5 w-4 rounded-[2px] border"
            style={{ borderColor: entry.color }}
          />
          {entry.label}
        </span>
      ))}
      <span className="text-[10px] text-ink-3">Boxes are drawn by the detector at capture time.</span>
    </div>
  );
}
