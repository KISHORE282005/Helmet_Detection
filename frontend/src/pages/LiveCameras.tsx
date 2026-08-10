/** Live Cameras and Camera Grid.
 *
 *  Both render the same tiles; the grid variant drops the chrome and widens
 *  the columns for a wall display. Column count follows the brief: four on a
 *  desktop, two on a laptop, one on a tablet.
 */

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { CameraTile, OfflineCameraAlert } from '../components/domain/CameraTile';
import {
  Button,
  CameraIcon,
  EmptyState,
  ErrorState,
  Panel,
  RefreshIcon,
  Select,
  Skeleton,
  StatusDot,
  cx,
} from '../components/ui/primitives';
import { useCameraMutations, useCameras, useIncidents } from '../lib/hooks';
import { relativeTime } from '../lib/format';
import type { Incident } from '../lib/types';

type Filter = 'all' | 'online' | 'offline' | 'unconfigured';

function useLatestByCamera() {
  // One recent page is enough to give each tile its last evidence frame.
  const { data } = useIncidents({ limit: 100 }, { refetchInterval: 15_000 });
  return useMemo(() => {
    const map = new Map<string, Incident>();
    for (const incident of data?.items ?? []) {
      if (!map.has(incident.camera_id)) map.set(incident.camera_id, incident);
    }
    return map;
  }, [data]);
}

export function LiveCameras({ wall = false }: { wall?: boolean }) {
  const { data, isLoading, isError, error, refetch } = useCameras();
  const { refresh } = useCameraMutations();
  const latest = useLatestByCamera();
  const [filter, setFilter] = useState<Filter>('all');

  const cameras = data?.items ?? [];
  const visible = cameras.filter((camera) =>
    filter === 'all' ? true : camera.stream_status === filter,
  );
  const offline = cameras.filter((camera) => camera.stream_status === 'offline');
  const online = cameras.filter((camera) => camera.stream_status === 'online');

  if (isError) {
    return (
      <>
        <PageHeader title={wall ? 'Camera Grid' : 'Live Cameras'} />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={wall ? 'Camera Grid' : 'Live Cameras'}
        subtitle={
          wall
            ? 'Full-width wall layout for the control-room monitor'
            : 'Connection state and the most recent AI evidence for each camera'
        }
        actions={
          <>
            <div className="flex items-center gap-3 text-[11px] text-ink-3">
              <StatusDot tone="good" size="sm" label={`${online.length} online`} />
              <StatusDot tone="critical" size="sm" label={`${offline.length} offline`} />
            </div>
            <Select
              value={filter}
              onChange={(event) => setFilter(event.target.value as Filter)}
              className="w-auto"
              aria-label="Filter cameras by state"
            >
              <option value="all">All cameras</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="unconfigured">No stream configured</option>
            </Select>
            <Button onClick={() => refresh.mutate()} disabled={refresh.isPending} size="sm">
              <RefreshIcon className={cx('h-3.5 w-3.5', refresh.isPending && 'animate-spin')} />
              Re-check
            </Button>
          </>
        }
      />

      <OfflineCameraAlert cameras={offline} />

      {data?.last_poll && (
        <p className="mb-3 text-[11px] text-ink-3">
          Reachability checked {relativeTime(data.last_poll)}, automatically every{' '}
          {data.poll_interval_seconds}s. A camera is reported online when its RTSP port
          accepts a connection — Phase 1 does not decode the stream itself.
        </p>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[4/3] w-full" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<CameraIcon className="h-6 w-6" />}
            title={
              cameras.length === 0
                ? 'No cameras registered'
                : 'No cameras match this filter'
            }
            description={
              cameras.length === 0
                ? 'Register your Hikvision cameras to monitor their connection state here.'
                : 'Change the filter, or re-check reachability.'
            }
            action={
              cameras.length === 0 ? (
                <Link to="/cameras">
                  <Button size="sm" variant="primary">
                    Add a camera
                  </Button>
                </Link>
              ) : (
                <Button size="sm" onClick={() => setFilter('all')}>
                  Show all cameras
                </Button>
              )
            }
          />
        </Panel>
      ) : (
        <div
          className={cx(
            'grid gap-3',
            // Tablet 1 · laptop 2 · desktop 4, per the control-room brief.
            'grid-cols-1 md:grid-cols-2',
            wall ? '2xl:grid-cols-4' : 'xl:grid-cols-3 2xl:grid-cols-4',
          )}
        >
          {visible.map((camera) => (
            <CameraTile
              key={camera.camera_id}
              camera={camera}
              lastIncident={latest.get(camera.camera_id)}
            />
          ))}
        </div>
      )}
    </>
  );
}

export default function LiveCamerasPage() {
  return <LiveCameras />;
}

export function CameraGridPage() {
  return <LiveCameras wall />;
}
