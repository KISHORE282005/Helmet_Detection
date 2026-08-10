/** The supervisor work queue: every incident still awaiting a decision. */

import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { IncidentCard } from '../components/domain/IncidentCard';
import { DetectionLegend } from '../components/domain/IncidentCard';
import {
  Badge,
  Button,
  CheckIcon,
  EmptyState,
  ErrorState,
  Panel,
  Skeleton,
} from '../components/ui/primitives';
import { useIncidents, REFRESH } from '../lib/hooks';
import { relativeTime } from '../lib/format';

export default function ActiveViolations() {
  const { data, isLoading, isError, error, refetch, dataUpdatedAt } = useIncidents(
    { status: 'Open', limit: 60 },
    { refetchInterval: REFRESH.live },
  );

  if (isError) {
    return (
      <>
        <PageHeader title="Active Safety Violations" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const incidents = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Active Safety Violations"
        subtitle="Confirmed incidents awaiting supervisor review"
        actions={
          <>
            {data && (
              <Badge tone={data.total > 0 ? 'critical' : 'good'}>
                {data.total} open
              </Badge>
            )}
            <span className="text-[11px] text-ink-3">
              Updated {relativeTime(new Date(dataUpdatedAt).toISOString())}
            </span>
            <Link to="/incidents">
              <Button size="sm">Full history</Button>
            </Link>
          </>
        }
      />

      {incidents.length > 0 && (
        <div className="mb-3 rounded-lg border border-line bg-surface px-3 py-2">
          <DetectionLegend />
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-80 w-full" />
          ))}
        </div>
      ) : incidents.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<CheckIcon className="h-7 w-7 text-good" />}
            title="Nothing awaiting review"
            description="Every confirmed helmet violation has been actioned. New incidents appear here the moment the AI confirms one."
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
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {incidents.map((incident) => (
            <IncidentCard key={incident.incident_id} incident={incident} />
          ))}
        </div>
      )}
    </>
  );
}
