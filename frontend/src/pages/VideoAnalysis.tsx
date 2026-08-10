/** Phase 1 input: analyse recorded CCTV footage.
 *
 *  Every counter on this page comes from the running pipeline. Before a job
 *  starts there is nothing to show, and the page says so rather than
 *  animating placeholder numbers.
 */

import { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { SuppressionMeter } from '../components/charts/charts';
import { EvidenceThumb } from '../components/domain/IncidentCard';
import {
  AlertIcon,
  Badge,
  Button,
  CheckIcon,
  EmptyState,
  Field,
  Panel,
  ProgressBar,
  Select,
  Skeleton,
  cx,
} from '../components/ui/primitives';
import { ApiError, api } from '../lib/api';
import {
  useAnalysisJob,
  useAnalysisJobs,
  useCameras,
  useIncidents,
} from '../lib/hooks';
import { bytes, duration, padded, relativeTime } from '../lib/format';
import type { AnalysisJob, Upload } from '../lib/types';

const ACCEPT = '.mp4,.avi,.mov,.mkv,.webm';

export default function VideoAnalysis() {
  const [upload, setUpload] = useState<Upload | null>(null);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState('');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const cameras = useCameras();
  const jobs = useAnalysisJobs();
  const job = useAnalysisJob(activeJobId);

  // Recover the running job after a page reload.
  const runningJob = jobs.data?.items.find(
    (item) => item.status === 'running' || item.status === 'queued',
  );
  const shownJob = job.data ?? runningJob ?? null;

  const handleFile = useCallback(async (file: File) => {
    setUploadError(null);
    setUploadPercent(0);
    setUpload(null);
    try {
      const result = await api.upload<Upload>('/api/analysis/upload', file, (fraction) =>
        setUploadPercent(fraction),
      );
      setUpload(result);
      setUploadPercent(null);
    } catch (error) {
      setUploadPercent(null);
      setUploadError(
        error instanceof ApiError ? error.message : 'The upload failed. Try again.',
      );
    }
  }, []);

  const start = async () => {
    if (!upload) return;
    setStarting(true);
    try {
      const created = await api.post<AnalysisJob>('/api/analysis/start', {
        upload_id: upload.upload_id,
        camera_id: cameraId || null,
      });
      setActiveJobId(created.job_id);
      setUpload(null);
      void jobs.refetch();
    } catch (error) {
      setUploadError(
        error instanceof ApiError ? error.message : 'The analysis could not be started.',
      );
    } finally {
      setStarting(false);
    }
  };

  const busy = Boolean(runningJob);

  return (
    <>
      <PageHeader
        title="Analyse Recorded Video"
        subtitle="Phase 1 input — the same pipeline that will run on live Hikvision streams in Phase 2"
        actions={
          shownJob && (
            <Badge
              tone={
                shownJob.status === 'running'
                  ? 'accent'
                  : shownJob.status === 'completed'
                    ? 'good'
                    : shownJob.status === 'failed'
                      ? 'critical'
                      : 'neutral'
              }
            >
              {shownJob.status}
            </Badge>
          )
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="flex flex-col gap-4 xl:col-span-2">
          {/* Upload */}
          {!shownJob || shownJob.status === 'completed' || shownJob.status === 'failed' ? (
            <Panel eyebrow="Step 1" title="Upload CCTV video">
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  const file = event.dataTransfer.files?.[0];
                  if (file) void handleFile(file);
                }}
                className={cx(
                  'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors',
                  dragging ? 'border-accent bg-accent-soft/40' : 'border-line-strong bg-surface-2',
                )}
              >
                <UploadIcon className="h-8 w-8 text-ink-3" />
                <p className="text-sm font-medium text-ink">Drag & drop video here</p>
                <p className="text-[11px] text-ink-3">MP4 · AVI · MOV · MKV · WEBM — up to 2 GB</p>
                <input
                  ref={inputRef}
                  type="file"
                  accept={ACCEPT}
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void handleFile(file);
                    event.target.value = '';
                  }}
                />
                <Button
                  variant="primary"
                  className="mt-1"
                  onClick={() => inputRef.current?.click()}
                  disabled={uploadPercent !== null}
                >
                  Select video
                </Button>
                {uploadPercent !== null && (
                  <div className="mt-2 w-full max-w-sm">
                    <ProgressBar value={uploadPercent} />
                    <p className="tabular mt-1 text-[11px] text-ink-3">
                      Uploading {Math.round(uploadPercent * 100)}%
                    </p>
                  </div>
                )}
                {uploadError && (
                  <p className="mt-2 flex items-center gap-1.5 text-[11px] text-critical">
                    <AlertIcon className="h-3.5 w-3.5" />
                    {uploadError}
                  </p>
                )}
              </div>

              {upload && (
                <div className="mt-4 rounded-lg border border-line bg-surface-2 p-3">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-ink">
                        {upload.filename}
                      </p>
                      <p className="text-[10px] text-ink-3">
                        Uploaded {relativeTime(upload.uploaded_at)}
                      </p>
                    </div>
                    <Badge tone="good" icon={<CheckIcon className="h-2.5 w-2.5" />}>
                      Ready
                    </Badge>
                  </div>

                  <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                    <Meta label="Duration" value={duration(upload.duration_seconds)} />
                    <Meta label="Resolution" value={upload.resolution} />
                    <Meta label="Source FPS" value={upload.fps ? upload.fps.toFixed(1) : '—'} />
                    <Meta label="Frames" value={upload.total_frames.toLocaleString('en-US')} />
                    <Meta label="Size" value={bytes(upload.size_bytes)} />
                  </dl>

                  <div className="mt-3 flex flex-wrap items-end gap-3 border-t border-line pt-3">
                    <Field
                      label="Attribute to camera"
                      hint="Leave unset to derive the camera from the filename or configured defaults."
                      className="min-w-[220px] flex-1"
                    >
                      <Select
                        value={cameraId}
                        onChange={(event) => setCameraId(event.target.value)}
                      >
                        <option value="">Detect from filename</option>
                        {cameras.data?.items.map((camera) => (
                          <option key={camera.camera_id} value={camera.camera_id}>
                            {camera.camera_id} — {camera.camera_name}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Button
                      variant="primary"
                      onClick={() => void start()}
                      disabled={starting || busy}
                      title={busy ? 'Another analysis is already running' : undefined}
                    >
                      {starting ? 'Starting…' : busy ? 'Queue behind running job' : 'Start AI analysis'}
                    </Button>
                  </div>
                </div>
              )}
            </Panel>
          ) : null}

          {/* Progress / results */}
          {shownJob && <JobPanel job={shownJob} onDismiss={() => setActiveJobId(null)} />}

          {!shownJob && !upload && (
            <Panel eyebrow="Pipeline" title="What happens when you start">
              <ol className="flex flex-col gap-2.5">
                {[
                  ['Detection', 'YOLO11 finds every person in each analysed frame.'],
                  ['Tracking', 'ByteTrack keeps one identity per person across frames.'],
                  [
                    'Violation',
                    'A person must read as helmet-missing for a run of consecutive frames before anything is raised.',
                  ],
                  [
                    'Incident',
                    'That confirmed run becomes exactly one incident — repeats for the same track are suppressed.',
                  ],
                  [
                    'Evidence',
                    'The best frame of the run is saved, scored on subject size, sharpness and confidence.',
                  ],
                ].map(([title, detail], index) => (
                  <li key={title} className="flex gap-3">
                    <span className="tabular mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-line-strong bg-surface-2 text-[10px] font-semibold text-ink-2">
                      {index + 1}
                    </span>
                    <div>
                      <p className="text-xs font-medium text-ink">{title}</p>
                      <p className="text-[11px] leading-relaxed text-ink-3">{detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </div>

        {/* History */}
        <Panel eyebrow="Runs" title="Analysis history" dense className="self-start">
          {jobs.isLoading ? (
            <div className="flex flex-col gap-2 p-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (jobs.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              compact
              title="No analysis has run yet"
              description="Completed runs are listed here with their incident counts."
            />
          ) : (
            <ul className="divide-y divide-line">
              {jobs.data?.items.map((item) => (
                <li key={item.job_id}>
                  <button
                    type="button"
                    onClick={() => setActiveJobId(item.job_id)}
                    className={cx(
                      'w-full px-3 py-2.5 text-left transition-colors hover:bg-surface-2',
                      activeJobId === item.job_id && 'bg-surface-2',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium text-ink">
                        {item.video.filename}
                      </span>
                      <Badge
                        tone={
                          item.status === 'completed'
                            ? 'good'
                            : item.status === 'running' || item.status === 'queued'
                              ? 'accent'
                              : item.status === 'failed'
                                ? 'critical'
                                : 'neutral'
                        }
                      >
                        {item.status}
                      </Badge>
                    </div>
                    <p className="tabular mt-1 text-[10px] text-ink-3">
                      {item.result
                        ? `${item.result.unique_incidents} incidents · ${item.result.raw_detections} raw detections`
                        : item.status === 'running'
                          ? `${Math.round(item.progress.progress * 100)}% complete`
                          : item.error ?? 'Not started'}
                    </p>
                    <p className="text-[10px] text-ink-3">
                      {relativeTime(item.finished_at ?? item.created_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}

/* ------------------------------------------------------------- Job panel */

function JobPanel({ job, onDismiss }: { job: AnalysisJob; onDismiss: () => void }) {
  const running = job.status === 'running' || job.status === 'queued';
  const progress = job.progress;

  if (job.status === 'failed') {
    return (
      <Panel eyebrow="Analysis" title="Analysis failed">
        <EmptyState
          icon={<AlertIcon className="h-6 w-6 text-critical" />}
          title={job.video.filename}
          description={job.error ?? 'The pipeline stopped with an unexpected error.'}
          action={
            <Button size="sm" onClick={onDismiss}>
              Dismiss
            </Button>
          }
        />
      </Panel>
    );
  }

  if (running) {
    return (
      <Panel
        eyebrow="Step 2"
        title="AI analysis in progress"
        action={
          <Button
            size="sm"
            variant="danger"
            onClick={() => void api.post(`/api/analysis/${job.job_id}/cancel`)}
          >
            Stop
          </Button>
        }
      >
        <div className="mb-1 flex items-baseline justify-between gap-3">
          <p className="truncate text-xs font-medium text-ink">{job.video.filename}</p>
          <span className="tabular text-sm font-semibold text-ink">
            {Math.round(progress.progress * 100)}%
          </span>
        </div>
        <ProgressBar
          value={progress.progress}
          indeterminate={job.status === 'queued'}
          className="h-2"
        />
        <p className="tabular mt-1.5 text-[11px] text-ink-3">
          {job.status === 'queued'
            ? 'Queued — waiting for the analysis worker'
            : `${progress.frames_read.toLocaleString('en-US')} / ${progress.frames_total.toLocaleString('en-US')} frames · ${progress.processing_fps.toFixed(1)} FPS processing · ${duration(progress.elapsed_seconds)} elapsed`}
        </p>

        <div className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3 sm:grid-cols-4">
          <LiveStat label="Frames analysed" value={progress.frames_analyzed.toLocaleString('en-US')} />
          <LiveStat label="People tracked" value={String(progress.people_detected)} />
          <LiveStat
            label="Raw detections"
            value={String(progress.raw_detections)}
            hint="helmet-missing person-frames"
          />
          <LiveStat
            label="Unique incidents"
            value={padded(progress.incidents)}
            tone="critical"
            hint="one per tracked person"
          />
        </div>
      </Panel>
    );
  }

  const result = job.result;
  if (!result) {
    return (
      <Panel eyebrow="Analysis" title={`Analysis ${job.status}`}>
        <EmptyState
          compact
          title={job.video.filename}
          description="The run ended before it produced a result."
          action={
            <Button size="sm" onClick={onDismiss}>
              Dismiss
            </Button>
          }
        />
      </Panel>
    );
  }

  return <ResultPanel job={job} onDismiss={onDismiss} />;
}

function ResultPanel({ job, onDismiss }: { job: AnalysisJob; onDismiss: () => void }) {
  const result = job.result!;
  const incidents = useIncidents({ analysis_id: job.job_id, limit: 12 });

  return (
    <>
      <Panel
        eyebrow="Step 3"
        title={
          <span className="flex items-center gap-2">
            Analysis complete
            <CheckIcon className="h-4 w-4 text-good" />
          </span>
        }
        action={
          <Button size="sm" onClick={onDismiss}>
            Dismiss
          </Button>
        }
      >
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <p className="truncate text-sm font-medium text-ink">{job.video.filename}</p>
          <p className="tabular text-[11px] text-ink-3">
            {duration(result.elapsed_seconds)} runtime · {result.processing_fps.toFixed(1)} FPS ·
            frame skip {result.frame_skip}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <ResultStat label="Duration" value={duration(job.video.duration_seconds)} />
          <ResultStat
            label="Frames analysed"
            value={result.frames_analyzed.toLocaleString('en-US')}
          />
          <ResultStat label="People detected" value={String(result.people_detected)} />
          <ResultStat
            label="Raw detections"
            value={String(result.raw_detections)}
          />
          <ResultStat
            label="Unique incidents"
            value={padded(result.unique_incidents)}
            tone="critical"
          />
          <ResultStat
            label="Compliant frames"
            value={result.compliant_frames.toLocaleString('en-US')}
            tone="good"
          />
        </div>
      </Panel>

      <Panel
        eyebrow="Duplicate suppression"
        title="Raw detections vs unique incidents"
      >
        <SuppressionMeter raw={result.raw_detections} unique={result.unique_incidents} />
        <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-ink-3">
          The pipeline saw{' '}
          <strong className="text-ink-2">
            {result.raw_detections.toLocaleString('en-US')}
          </strong>{' '}
          helmet-missing person-frames and recorded{' '}
          <strong className="text-ink-2">{result.unique_incidents}</strong> incident
          {result.unique_incidents === 1 ? '' : 's'}. The difference is the same people
          seen again across frames — collapsed by track identity so one worker never
          generates hundreds of records.
        </p>
      </Panel>

      {(incidents.data?.items.length ?? 0) > 0 && (
        <Panel
          eyebrow="Output"
          title={`Incidents from this run (${incidents.data?.total ?? 0})`}
          action={
            <Link to={`/incidents?analysis=${job.job_id}`}>
              <Button size="sm" variant="ghost">
                Open in history
              </Button>
            </Link>
          }
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-6">
            {incidents.data?.items.map((incident) => (
              <Link
                key={incident.incident_id}
                to={`/incidents/${incident.incident_id}`}
                className="group"
              >
                <EvidenceThumb
                  incident={incident}
                  className="aspect-video w-full transition-opacity group-hover:opacity-80"
                />
                <p className="tabular mt-1 truncate text-[10px] font-medium text-ink">
                  {incident.incident_id}
                </p>
                <p className="tabular truncate text-[10px] text-ink-3">
                  {incident.video_time} · track #{incident.track_id}
                </p>
              </Link>
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}

/* ----------------------------------------------------------------- Bits */

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow truncate">{label}</dt>
      <dd className="tabular truncate text-xs font-medium text-ink">{value}</dd>
    </div>
  );
}

function LiveStat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: 'critical';
}) {
  return (
    <div className="min-w-0">
      <div className="eyebrow truncate">{label}</div>
      <div
        className={cx(
          'tabular mt-0.5 text-xl font-semibold',
          tone === 'critical' ? 'text-critical' : 'text-ink',
        )}
      >
        {value}
      </div>
      {hint && <div className="truncate text-[10px] text-ink-3">{hint}</div>}
    </div>
  );
}

function ResultStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'critical' | 'good';
}) {
  return (
    <div className="min-w-0 rounded border border-line bg-surface-2 p-2.5">
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

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 16.5V4.2M7.6 8.6 12 4.2l4.4 4.4" />
      <path d="M4 15.6v3a1.8 1.8 0 0 0 1.8 1.8h12.4a1.8 1.8 0 0 0 1.8-1.8v-3" />
    </svg>
  );
}
