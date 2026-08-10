/** Evidence gallery — visual triage across incidents. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { EvidenceThumb, DetectionLegend } from '../components/domain/IncidentCard';
import {
  Badge,
  Button,
  DownloadIcon,
  EmptyState,
  ErrorState,
  Field,
  ImageIcon,
  LinkButton,
  Modal,
  Panel,
  Select,
  Skeleton,
  StatusBadge,
} from '../components/ui/primitives';
import { mediaUrl } from '../lib/api';
import { useIncidentFilters, useIncidents } from '../lib/hooks';
import { confidencePercent, dateTime, shortDate } from '../lib/format';
import type { Incident } from '../lib/types';

export default function Evidence() {
  const [camera, setCamera] = useState('');
  const [status, setStatus] = useState('');
  const [limit, setLimit] = useState(48);
  const [selected, setSelected] = useState<Incident | null>(null);

  const options = useIncidentFilters();
  const { data, isLoading, isError, error, refetch } = useIncidents({
    camera_id: camera || undefined,
    status: status || undefined,
    limit,
  });

  const items = data?.items ?? [];
  const withImages = items.filter((incident) => incident.evidence);

  return (
    <>
      <PageHeader
        title="Evidence Gallery"
        subtitle="Best captured frame for each confirmed incident"
        actions={
          <>
            <Field label="Camera">
              <Select value={camera} onChange={(event) => setCamera(event.target.value)}>
                <option value="">All cameras</option>
                {options.data?.cameras.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">Any status</option>
                {options.data?.statuses.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            </Field>
          </>
        }
      />

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2">
        <DetectionLegend />
        {data && (
          <span className="text-[11px] text-ink-3">
            {withImages.length} of {data.total} incidents have a stored image
          </span>
        )}
      </div>

      {isError ? (
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      ) : isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 10 }, (_, i) => (
            <Skeleton key={i} className="aspect-[4/3] w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<ImageIcon className="h-7 w-7" />}
            title="No evidence to show"
            description="Evidence images are written when the AI confirms a violation. Analyse a recording to populate the gallery."
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
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {items.map((incident) => (
              <button
                key={incident.incident_id}
                type="button"
                onClick={() => setSelected(incident)}
                className="group flex flex-col overflow-hidden rounded-lg border border-line bg-surface text-left transition-colors hover:border-line-strong"
              >
                <div className="relative aspect-[4/3] w-full bg-plane">
                  <EvidenceThumb
                    incident={incident}
                    className="h-full w-full rounded-none border-0 transition-opacity group-hover:opacity-85"
                  />
                  <div className="absolute right-1.5 top-1.5">
                    <Badge tone="critical">{confidencePercent(incident.confidence)}</Badge>
                  </div>
                </div>
                <div className="p-2">
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="tabular truncate text-[11px] font-semibold text-ink">
                      {incident.incident_id}
                    </span>
                    <span className="tabular shrink-0 text-[10px] text-ink-3">
                      {incident.video_time}
                    </span>
                  </div>
                  <p className="truncate text-[10px] text-ink-2">
                    {incident.camera_id} · {incident.location || incident.camera_name}
                  </p>
                  <p className="truncate text-[10px] text-ink-3">{incident.violation_type}</p>
                </div>
              </button>
            ))}
          </div>

          {data && items.length < data.total && (
            <div className="mt-4 flex justify-center">
              <Button onClick={() => setLimit((value) => value + 48)}>
                Load more ({data.total - items.length} remaining)
              </Button>
            </div>
          )}
        </>
      )}

      <Modal
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.incident_id} — ${selected.violation_type}` : ''}
        subtitle={
          selected
            ? `${selected.camera_id} · ${selected.location || selected.camera_name} · video ${selected.video_time}`
            : undefined
        }
        width="max-w-5xl"
      >
        {selected && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              {selected.evidence ? (
                <img
                  src={mediaUrl('evidence', selected.evidence)}
                  alt={`Evidence for ${selected.incident_id}`}
                  className="w-full rounded border border-line bg-plane object-contain"
                />
              ) : (
                <EmptyState title="The image file is missing from output/images" />
              )}
              <div className="mt-2">
                <DetectionLegend />
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <dl className="flex flex-col divide-y divide-line rounded border border-line bg-surface-2 px-3">
                <Row label="Status" value={<StatusBadge status={selected.status} />} />
                <Row label="Confidence" value={confidencePercent(selected.confidence)} />
                <Row label="Track" value={`#${selected.track_id}`} />
                <Row label="Date" value={shortDate(selected.date)} />
                <Row label="Recorded" value={dateTime(selected.detected_at)} />
                <Row label="People in frame" value={String(selected.scene_persons)} />
                <Row label="Without helmet" value={String(selected.scene_no_helmet)} />
                <Row label="Source" value={selected.video_name || 'Unknown'} />
              </dl>
              <div className="flex flex-wrap gap-2">
                <Link to={`/incidents/${selected.incident_id}`}>
                  <Button variant="primary" size="sm">
                    Open full review
                  </Button>
                </Link>
                {selected.evidence && (
                  <LinkButton
                    href={mediaUrl('evidence', selected.evidence, true)}
                    size="sm"
                    download
                  >
                    <DownloadIcon className="h-3.5 w-3.5" />
                    Download
                  </LinkButton>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2">
      <dt className="text-[11px] text-ink-3">{label}</dt>
      <dd className="tabular truncate text-xs font-medium text-ink">{value}</dd>
    </div>
  );
}
