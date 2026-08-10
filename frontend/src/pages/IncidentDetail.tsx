/** Incident review: the evidence, everything known about it, and the decision. */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import {
  DetectionHierarchy,
  DetectionLegend,
  EvidenceThumb,
} from '../components/domain/IncidentCard';
import {
  AlertIcon,
  Badge,
  Button,
  CheckIcon,
  DownloadIcon,
  ErrorState,
  ImageIcon,
  LinkButton,
  Panel,
  Skeleton,
  StatusBadge,
  cx,
} from '../components/ui/primitives';
import { mediaUrl } from '../lib/api';
import { useIncident, useReviewIncident } from '../lib/hooks';
import { confidencePercent, dateTime, shortDate } from '../lib/format';
import type { IncidentStatus } from '../lib/types';

export default function IncidentDetail() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const navigate = useNavigate();
  const { data: incident, isLoading, isError, error, refetch } = useIncident(incidentId);
  const review = useReviewIncident();

  const [remarks, setRemarks] = useState('');
  const [view, setView] = useState<'evidence' | 'poster'>('evidence');

  // Reset the form when the route moves to a different incident.
  useEffect(() => {
    setRemarks(incident?.remarks ?? '');
    setView('evidence');
  }, [incident?.incident_id, incident?.remarks]);

  if (isError) {
    return (
      <>
        <PageHeader title="Incident" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  if (isLoading || !incident) {
    return (
      <>
        <PageHeader title="Incident" />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <Skeleton className="aspect-video w-full xl:col-span-2" />
          <Skeleton className="h-96 w-full" />
        </div>
      </>
    );
  }

  const submit = (status: IncidentStatus) =>
    review.mutate({
      incidentId: incident.incident_id,
      status,
      reviewed_by: 'Safety Supervisor',
      remarks: remarks || undefined,
    });

  const activeImage = view === 'poster' ? incident.poster : incident.evidence;

  return (
    <>
      <PageHeader
        title={`Incident ${incident.incident_id}`}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone="critical" icon={<AlertIcon className="h-2.5 w-2.5" />}>
              {incident.violation_type}
            </Badge>
            <StatusBadge status={incident.status} />
            <span className="text-ink-3">
              {incident.camera_id} · {incident.location || incident.camera_name} ·{' '}
              video {incident.video_time}
            </span>
          </span>
        }
        actions={
          <>
            <Button size="sm" onClick={() => navigate(-1)}>
              Back
            </Button>
            <Link to="/violations">
              <Button size="sm">Review queue</Button>
            </Link>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Evidence */}
        <div className="flex flex-col gap-4 xl:col-span-2">
          <Panel
            eyebrow="Evidence"
            title="Captured frame"
            action={
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant={view === 'evidence' ? 'primary' : 'ghost'}
                  onClick={() => setView('evidence')}
                  disabled={!incident.evidence}
                >
                  Detection frame
                </Button>
                <Button
                  size="sm"
                  variant={view === 'poster' ? 'primary' : 'ghost'}
                  onClick={() => setView('poster')}
                  disabled={!incident.poster}
                  title={incident.poster ? undefined : 'No warning poster was generated'}
                >
                  Warning poster
                </Button>
              </div>
            }
          >
            {activeImage ? (
              <figure>
                <a
                  href={mediaUrl(view, activeImage)}
                  target="_blank"
                  rel="noreferrer"
                  className="block overflow-hidden rounded border border-line bg-plane"
                >
                  <img
                    src={mediaUrl(view, activeImage)}
                    alt={`${view === 'poster' ? 'Warning poster' : 'Detection frame'} for ${incident.incident_id}`}
                    className="max-h-[62vh] w-full object-contain"
                  />
                </a>
                <figcaption className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
                  <DetectionLegend />
                  <span className="text-[10px] text-ink-3">Select the image to open it full size</span>
                </figcaption>
              </figure>
            ) : (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded border border-line bg-plane text-center">
                <ImageIcon className="h-7 w-7 text-ink-3" />
                <p className="text-xs text-ink-2">
                  {view === 'poster'
                    ? 'No warning poster was generated for this incident'
                    : 'The evidence image is no longer on disk'}
                </p>
                <p className="max-w-sm text-[10px] text-ink-3">
                  The database record remains complete; only the image file is missing
                  from the output folder.
                </p>
              </div>
            )}
          </Panel>

          {/* Scene breakdown — detection vs violation vs incident */}
          <Panel eyebrow="Scene at capture" title="What the AI saw in this frame">
            <div className="grid grid-cols-3 gap-3">
              <SceneStat
                label="People in frame"
                value={incident.scene_persons}
                tone="accent"
              />
              <SceneStat
                label="Wearing a helmet"
                value={incident.scene_helmet}
                tone="good"
              />
              <SceneStat
                label="Without a helmet"
                value={incident.scene_no_helmet}
                tone="critical"
              />
            </div>
            <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-ink-3">
              This incident records <strong className="text-ink-2">one</strong> tracked
              person (#{incident.track_id}). Where several people were confirmed in the
              same moment, they share this evidence frame rather than generating a
              record each.
            </p>
          </Panel>
        </div>

        {/* Facts + decision */}
        <div className="flex flex-col gap-4">
          <Panel eyebrow="Incident" title="Information">
            <dl className="flex flex-col divide-y divide-line">
              <Row label="Incident ID" value={incident.incident_id} mono />
              <Row label="Camera" value={`${incident.camera_id} — ${incident.camera_name}`} />
              <Row label="Location" value={incident.location || 'Not assigned'} />
              <Row label="Date" value={shortDate(incident.date)} />
              <Row label="Video time" value={incident.video_time} mono />
              <Row label="Recorded at" value={dateTime(incident.detected_at)} />
              <Row label="Violation" value={incident.violation_type} />
              <Row label="Confidence" value={confidencePercent(incident.confidence)} mono />
              <Row label="Track ID" value={`#${incident.track_id}`} mono />
              <Row label="Source" value={incident.video_name || 'Unknown'} />
              <Row label="Status" value={<StatusBadge status={incident.status} />} />
              {incident.reviewed_at && (
                <Row
                  label="Reviewed"
                  value={`${dateTime(incident.reviewed_at)}${incident.reviewed_by ? ` by ${incident.reviewed_by}` : ''}`}
                />
              )}
            </dl>
          </Panel>

          <Panel eyebrow="Pipeline" title="How this record was produced">
            <DetectionHierarchy incident={incident} />
          </Panel>

          <Panel eyebrow="Decision" title="Review this incident">
            <label className="mb-3 flex flex-col gap-1">
              <span className="text-[11px] font-medium text-ink-2">Comment</span>
              <textarea
                value={remarks}
                onChange={(event) => setRemarks(event.target.value)}
                rows={3}
                placeholder="Optional note for the safety record"
                className="w-full resize-y rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
              />
            </label>

            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="primary"
                onClick={() => submit('Confirmed')}
                disabled={review.isPending}
              >
                <CheckIcon className="h-3.5 w-3.5" />
                Confirm violation
              </Button>
              <Button onClick={() => submit('False Positive')} disabled={review.isPending}>
                Mark false positive
              </Button>
              <Button onClick={() => submit('Resolved')} disabled={review.isPending}>
                Mark resolved
              </Button>
              <Button onClick={() => submit('Open')} disabled={review.isPending}>
                Reopen
              </Button>
            </div>

            {review.isError && (
              <p className="mt-2 text-[11px] text-critical">
                {review.error instanceof Error ? review.error.message : 'Could not save the review'}
              </p>
            )}
            {review.isSuccess && (
              <p className="mt-2 text-[11px] text-good">Review saved.</p>
            )}

            <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
              {incident.evidence && (
                <LinkButton
                  href={mediaUrl('evidence', incident.evidence, true)}
                  size="sm"
                  download
                >
                  <DownloadIcon className="h-3.5 w-3.5" />
                  Download evidence
                </LinkButton>
              )}
              {incident.poster && (
                <LinkButton href={mediaUrl('poster', incident.poster, true)} size="sm" download>
                  <DownloadIcon className="h-3.5 w-3.5" />
                  Download poster
                </LinkButton>
              )}
            </div>
          </Panel>

          {incident.related && incident.related.length > 0 && (
            <Panel
              eyebrow="Same analysis run"
              title={`${incident.related.length} other incident${incident.related.length > 1 ? 's' : ''}`}
            >
              <div className="grid grid-cols-3 gap-2">
                {incident.related.slice(0, 9).map((related) => (
                  <Link
                    key={related.incident_id}
                    to={`/incidents/${related.incident_id}`}
                    className="group"
                    title={`${related.incident_id} · ${related.video_time}`}
                  >
                    <EvidenceThumb
                      incident={related}
                      className="aspect-video w-full transition-opacity group-hover:opacity-80"
                    />
                    <p className="tabular mt-1 truncate text-[10px] text-ink-3">
                      {related.incident_id}
                    </p>
                  </Link>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="shrink-0 text-[11px] text-ink-3">{label}</dt>
      <dd
        className={cx(
          'min-w-0 truncate text-right text-xs font-medium text-ink',
          mono && 'tabular',
        )}
        title={typeof value === 'string' ? value : undefined}
      >
        {value}
      </dd>
    </div>
  );
}

function SceneStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: 'accent' | 'good' | 'critical';
}) {
  return (
    <div className="rounded border border-line bg-surface-2 p-2.5">
      <div className="eyebrow truncate">{label}</div>
      <div
        className={cx(
          'mt-1 text-xl font-semibold',
          tone === 'accent' && 'text-ink',
          tone === 'good' && 'text-good',
          tone === 'critical' && 'text-critical',
        )}
      >
        {value}
      </div>
    </div>
  );
}
