/** Safety Overview — the page that must answer, within five seconds:
 *  how many cameras are up, is anything open, where, when, and can I see it.
 */

import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { StatTile, NoDataValue } from '../components/domain/StatTile';
import { CameraTile, OfflineCameraAlert } from '../components/domain/CameraTile';
import { TrendChart } from '../components/charts/charts';
import {
  Button,
  CameraIcon,
  EmptyState,
  ErrorState,
  Panel,
  RefreshIcon,
  Skeleton,
  cx,
} from '../components/ui/primitives';
import { useCameraMutations, useDashboard } from '../lib/hooks';
import { labelDay, padded, percent, relativeTime } from '../lib/format';
import type { Incident } from '../lib/types';

export default function Dashboard() {
  const { data, isLoading, isError, error, refetch } = useDashboard();
  const { refresh } = useCameraMutations();

  if (isError) {
    return (
      <>
        <PageHeader title="Safety Overview" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const cameras = data?.cameras;
  const offlineCameras = (data?.camera_status ?? []).filter(
    (camera) => camera.stream_status === 'offline',
  );

  // Latest evidence per camera, so a tile can show what the AI last caught there.
  const latestByCamera = new Map<string, Incident>();
  for (const incident of data?.latest_incidents ?? []) {
    if (!latestByCamera.has(incident.camera_id)) {
      latestByCamera.set(incident.camera_id, incident);
    }
  }

  const trend = (data?.week.trend ?? []).map((point) => ({
    date: point.key,
    count: point.count,
    label: labelDay(point.key),
  }));

  const hasAnyData = (data?.week.violations ?? 0) > 0 || (data?.today.violations ?? 0) > 0;

  return (
    <>
      <PageHeader
        title="Safety Overview"
        subtitle="Real-time PPE compliance across manufacturing areas"
        actions={
          <>
            <span className="hidden text-[11px] text-ink-3 sm:block">
              {data?.cameras.last_poll
                ? `Cameras checked ${relativeTime(data.cameras.last_poll)}`
                : 'Camera check pending'}
            </span>
            <Button
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending}
              size="sm"
            >
              <RefreshIcon className={cx('h-3.5 w-3.5', refresh.isPending && 'animate-spin')} />
              Re-check cameras
            </Button>
          </>
        }
      />

      <OfflineCameraAlert cameras={offlineCameras} />

      {/* KPI row */}
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Cameras Online"
          loading={isLoading}
          value={
            cameras ? (
              <>
                {cameras.online}
                <span className="text-lg font-normal text-ink-3"> / {cameras.total}</span>
              </>
            ) : (
              <NoDataValue />
            )
          }
          tone={
            !cameras || cameras.total === 0
              ? 'neutral'
              : cameras.offline > 0
                ? 'critical'
                : cameras.online > 0
                  ? 'good'
                  : 'warning'
          }
          footnote={
            cameras
              ? cameras.unconfigured > 0
                ? `${cameras.unconfigured} without an RTSP endpoint`
                : `${cameras.offline} offline`
              : undefined
          }
          status={
            cameras && cameras.online > 0
              ? { tone: 'good', label: `${cameras.online} reachable` }
              : undefined
          }
        />

        <StatTile
          label="Active Violations"
          loading={isLoading}
          value={padded(data?.active_violations.count ?? 0)}
          tone={data?.active_violations.count ? 'critical' : 'good'}
          footnote={
            data?.active_violations.count
              ? 'Requires supervisor review'
              : 'Nothing awaiting review'
          }
        />

        <StatTile
          label="Today's Violations"
          loading={isLoading}
          value={padded(data?.today.violations ?? 0)}
          tone={data?.today.violations ? 'warning' : 'neutral'}
          delta={data?.today.delta_percent}
          deltaLabel="vs yesterday"
          upIsGood={false}
          trend={trend.map((t) => t.count)}
        />

        <StatTile
          label="Compliance Rate"
          loading={isLoading}
          value={
            data?.compliance.rate === null || data?.compliance.rate === undefined ? (
              <NoDataValue />
            ) : (
              percent(data.compliance.rate)
            )
          }
          tone={
            data?.compliance.rate === null || data?.compliance.rate === undefined
              ? 'neutral'
              : data.compliance.rate >= 95
                ? 'good'
                : data.compliance.rate >= 85
                  ? 'warning'
                  : 'critical'
          }
          delta={data?.compliance.rate === null ? undefined : data?.compliance.delta}
          deltaLabel="vs yesterday"
          upIsGood
          footnote={
            data?.compliance.rate === null
              ? 'No footage analysed today'
              : `${data?.compliance.people_detected ?? 0} people tracked today`
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* Live monitoring — the visual centrepiece */}
        <div className="flex flex-col gap-4 xl:col-span-2">
          <Panel
            eyebrow="Monitoring"
            title="Camera Wall"
            action={
              <Link to="/grid">
                <Button size="sm" variant="ghost">
                  Full grid
                </Button>
              </Link>
            }
          >
            {isLoading ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="aspect-video w-full" />
                ))}
              </div>
            ) : (data?.camera_status.length ?? 0) === 0 ? (
              <EmptyState
                icon={<CameraIcon className="h-6 w-6" />}
                title="No cameras registered"
                description="Add your Hikvision cameras so the operations centre can track their connection state."
                action={
                  <Link to="/cameras">
                    <Button size="sm" variant="primary">
                      Add a camera
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {data?.camera_status.slice(0, 4).map((camera) => (
                  <CameraTile
                    key={camera.camera_id}
                    camera={camera}
                    lastIncident={latestByCamera.get(camera.camera_id)}
                    compact
                  />
                ))}
              </div>
            )}
          </Panel>

          <Panel
            eyebrow="Last 7 days"
            title="Violation Trend"
            action={
              <Link to="/analytics">
                <Button size="sm" variant="ghost">
                  Analytics
                </Button>
              </Link>
            }
          >
            {isLoading ? (
              <Skeleton className="h-[180px] w-full" />
            ) : hasAnyData ? (
              <TrendChart points={trend} />
            ) : (
              <EmptyState
                compact
                title="No violations recorded in the last 7 days"
                description="The trend fills in as soon as an analysis run confirms its first incident."
              />
            )}
          </Panel>
       

        </div>
      </div>
    </>
  );
}
