/** Live camera panel.
 *
 *  Phase 1 has no decoded RTSP stream, so this panel never pretends to show
 *  moving video. It shows the camera's real transport state and, when the
 *  camera has produced a violation, the most recent annotated frame the AI
 *  actually captured — labelled as evidence, not as a live feed.
 */

import { Link } from 'react-router-dom';
import { mediaUrl } from '../../lib/api';
import { clockTime, padded, relativeTime } from '../../lib/format';
import type { Camera, Incident } from '../../lib/types';
import {
  Badge,
  CameraIcon,
  StatusDot,
  cx,
  type Tone,
} from '../ui/primitives';

export function streamTone(camera: Camera): Tone {
  switch (camera.stream_status) {
    case 'online':
      return 'good';
    case 'offline':
      return 'critical';
    default:
      return 'neutral';
  }
}

export function streamLabel(camera: Camera): string {
  switch (camera.stream_status) {
    case 'online':
      return 'LIVE';
    case 'offline':
      return 'OFFLINE';
    case 'unconfigured':
      return 'NO STREAM';
    default:
      return 'UNKNOWN';
  }
}

export function CameraTile({
  camera,
  lastIncident,
  compact,
}: {
  camera: Camera;
  lastIncident?: Incident;
  compact?: boolean;
}) {
  const tone = streamTone(camera);
  const online = camera.stream_status === 'online';
  const offline = camera.stream_status === 'offline';

  return (
    <article
      className={cx(
        'flex min-w-0 flex-col overflow-hidden rounded-lg border bg-surface',
        offline ? 'border-critical/45' : 'border-line',
      )}
    >
      <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <StatusDot tone={tone} pulse={online} />
          <span
            className={cx(
              'text-[10px] font-bold tracking-wider',
              tone === 'good' && 'text-good',
              tone === 'critical' && 'text-critical',
              tone === 'neutral' && 'text-ink-3',
            )}
          >
            {streamLabel(camera)}
          </span>
          <span className="tabular truncate text-[11px] font-semibold text-ink">
            {camera.camera_id}
          </span>
        </div>
        {camera.violations_today > 0 && (
          <Badge tone="critical">{padded(camera.violations_today)} today</Badge>
        )}
      </header>

      <div className="relative aspect-video w-full bg-plane">
        {lastIncident?.evidence ? (
          <>
            <img
              src={mediaUrl('evidence', lastIncident.evidence)}
              alt={`Last confirmed violation on ${camera.camera_id}`}
              loading="lazy"
              className="h-full w-full object-cover opacity-90"
            />
            <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 bg-gradient-to-b from-black/75 to-transparent p-2">
              <Badge tone="critical">Last evidence frame</Badge>
              <span className="tabular rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-ink-2">
                {lastIncident.video_time}
              </span>
            </div>
          </>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
            <CameraIcon className="h-7 w-7 text-ink-3" />
            <p className="text-[11px] font-medium text-ink-2">
              {offline
                ? 'Stream unreachable'
                : online
                  ? 'Connected — video decoding arrives in Phase 2'
                  : 'No RTSP endpoint configured'}
            </p>
            <p className="max-w-[26ch] text-[10px] leading-relaxed text-ink-3">
              {offline
                ? `Last reachable ${camera.last_seen ? relativeTime(camera.last_seen) : 'never'}.`
                : 'Analyse recorded footage from this camera on the Video Analysis page.'}
            </p>
          </div>
        )}

        {/* Scan-line texture keeps the panel reading as a monitor without
            implying a moving picture. */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              'repeating-linear-gradient(180deg, #fff 0px, #fff 1px, transparent 1px, transparent 3px)',
          }}
        />
      </div>

      <div className="border-t border-line px-3 py-2">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-xs font-medium text-ink" title={camera.camera_name}>
            {camera.camera_name}
          </p>
          {camera.ai_enabled ? (
            <span className="shrink-0 text-[10px] font-medium text-accent">AI enabled</span>
          ) : (
            <span className="shrink-0 text-[10px] text-ink-3">AI off</span>
          )}
        </div>
        <p className="truncate text-[10px] text-ink-3">
          {camera.location || camera.area || camera.department || 'Location not set'}
        </p>

        {!compact && (
          <dl className="mt-2 grid grid-cols-3 gap-2 border-t border-line pt-2 text-[10px]">
            <Metric label="Transport" value={camera.ip_address ? 'RTSP' : 'File'} />
            <Metric
              label="Target FPS"
              value={camera.target_fps ? `${camera.target_fps}` : '—'}
            />
            <Metric
              label="Checked"
              value={camera.last_seen ? clockTime(camera.last_seen) : '—'}
            />
          </dl>
        )}
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-ink-3">{label}</dt>
      <dd className="tabular truncate font-medium text-ink-2">{value}</dd>
    </div>
  );
}

/** Offline banner used above the grid when cameras drop out. */
export function OfflineCameraAlert({ cameras }: { cameras: Camera[] }) {
  if (cameras.length === 0) return null;
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-critical/40 bg-critical/8 px-3 py-2.5">
      <StatusDot tone="critical" pulse />
      <span className="text-xs font-semibold text-critical">
        {cameras.length} camera{cameras.length > 1 ? 's' : ''} unreachable
      </span>
      <span className="text-[11px] text-ink-2">
        {cameras.map((c) => c.camera_id).join(', ')} — no response on the RTSP port.
      </span>
      <Link
        to="/cameras"
        className="ml-auto text-[11px] font-medium text-accent underline-offset-2 hover:underline"
      >
        Open camera management
      </Link>
    </div>
  );
}
