/** Searchable, filterable incident table. */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/layout/AppShell';
import { EvidenceThumb } from '../components/domain/IncidentCard';
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Panel,
  SearchIcon,
  Select,
  Skeleton,
  StatusBadge,
  TextInput,
  cx,
} from '../components/ui/primitives';
import { useIncidentFilters, useIncidents, type IncidentQuery } from '../lib/hooks';
import { confidencePercent, dateTime, isoDay, shortDate } from '../lib/format';

const PAGE_SIZE = 25;

const EMPTY: IncidentQuery = {
  search: '',
  camera_id: '',
  location: '',
  status: '',
  date_from: '',
  date_to: '',
  min_confidence: undefined,
};

export default function IncidentHistory() {
  const [filters, setFilters] = useState<IncidentQuery>(EMPTY);
  const [page, setPage] = useState(0);
  const options = useIncidentFilters();

  const query: IncidentQuery = {
    ...filters,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };
  const { data, isLoading, isError, error, refetch, isFetching } = useIncidents(query);

  const update = (patch: Partial<IncidentQuery>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(0);
  };

  const activeFilterCount = Object.entries(filters).filter(
    ([, value]) => value !== '' && value !== undefined,
  ).length;

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Incident History"
        subtitle="Every confirmed violation — one record per tracked person, never per frame"
        actions={
          <>
            <span className="text-[11px] text-ink-3">
              {isFetching ? 'Loading…' : `${total.toLocaleString('en-US')} incidents`}
            </span>
            {activeFilterCount > 0 && (
              <Button size="sm" onClick={() => { setFilters(EMPTY); setPage(0); }}>
                Clear filters
              </Button>
            )}
          </>
        }
      />

      {/* Filters — one row above the table, per the interaction spec. */}
      <div className="mb-3 grid grid-cols-1 gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-2 lg:grid-cols-6">
        <Field label="Search" className="sm:col-span-2">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
            <TextInput
              value={filters.search ?? ''}
              onChange={(event) => update({ search: event.target.value })}
              placeholder="Incident ID, camera, location, video"
              className="pl-7"
            />
          </div>
        </Field>

        <Field label="Camera">
          <Select
            value={filters.camera_id ?? ''}
            onChange={(event) => update({ camera_id: event.target.value })}
          >
            <option value="">All cameras</option>
            {options.data?.cameras.map((camera) => (
              <option key={camera} value={camera}>
                {camera}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Location">
          <Select
            value={filters.location ?? ''}
            onChange={(event) => update({ location: event.target.value })}
          >
            <option value="">All locations</option>
            {options.data?.locations.map((location) => (
              <option key={location} value={location}>
                {location}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Status">
          <Select
            value={filters.status ?? ''}
            onChange={(event) => update({ status: event.target.value })}
          >
            <option value="">Any status</option>
            {options.data?.statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Minimum confidence">
          <Select
            value={filters.min_confidence ?? ''}
            onChange={(event) =>
              update({
                min_confidence: event.target.value ? Number(event.target.value) : undefined,
              })
            }
          >
            <option value="">Any</option>
            <option value="0.7">70% and above</option>
            <option value="0.8">80% and above</option>
            <option value="0.9">90% and above</option>
            <option value="0.95">95% and above</option>
          </Select>
        </Field>

        <Field label="From date">
          <TextInput
            type="date"
            value={filters.date_from ?? ''}
            max={filters.date_to || isoDay()}
            onChange={(event) => update({ date_from: event.target.value })}
          />
        </Field>

        <Field label="To date">
          <TextInput
            type="date"
            value={filters.date_to ?? ''}
            min={filters.date_from || undefined}
            onChange={(event) => update({ date_to: event.target.value })}
          />
        </Field>

        <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4">
          <Button
            size="sm"
            onClick={() => update({ date_from: isoDay(), date_to: isoDay() })}
          >
            Today
          </Button>
          <Button
            size="sm"
            onClick={() => update({ date_from: isoDay(-6), date_to: isoDay() })}
          >
            Last 7 days
          </Button>
          <Button
            size="sm"
            onClick={() => update({ date_from: isoDay(-29), date_to: isoDay() })}
          >
            Last 30 days
          </Button>
        </div>
      </div>

      <Panel dense>
        {isError ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : isLoading ? (
          <div className="flex flex-col gap-2 p-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-11 w-full" />
            ))}
          </div>
        ) : (data?.items.length ?? 0) === 0 ? (
          <EmptyState
            icon={<SearchIcon className="h-6 w-6" />}
            title={activeFilterCount > 0 ? 'No incidents match these filters' : 'No incidents recorded yet'}
            description={
              activeFilterCount > 0
                ? 'Widen the date range or clear a filter to see more.'
                : 'Run an analysis on recorded footage and confirmed violations will be listed here.'
            }
            action={
              activeFilterCount > 0 ? (
                <Button size="sm" onClick={() => { setFilters(EMPTY); setPage(0); }}>
                  Clear filters
                </Button>
              ) : (
                <Link to="/analysis">
                  <Button size="sm" variant="primary">
                    Analyse footage
                  </Button>
                </Link>
              )
            }
          />
        ) : (
          <>
            {/* The table is the only thing allowed to scroll sideways. */}
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-3">
                    <Th className="w-16">Evidence</Th>
                    <Th>Incident</Th>
                    <Th>Date</Th>
                    <Th>Video time</Th>
                    <Th>Camera</Th>
                    <Th>Location</Th>
                    <Th>Violation</Th>
                    <Th className="text-right">Confidence</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((incident) => (
                    <tr
                      key={incident.incident_id}
                      className="border-b border-line transition-colors last:border-b-0 hover:bg-surface-2"
                    >
                      <Td>
                        <Link to={`/incidents/${incident.incident_id}`}>
                          <EvidenceThumb incident={incident} className="h-9 w-14" />
                        </Link>
                      </Td>
                      <Td>
                        <Link
                          to={`/incidents/${incident.incident_id}`}
                          className="tabular text-xs font-semibold text-accent hover:underline"
                        >
                          {incident.incident_id}
                        </Link>
                        <div className="text-[10px] text-ink-3">
                          Track #{incident.track_id}
                        </div>
                      </Td>
                      <Td className="tabular whitespace-nowrap text-xs text-ink-2">
                        {shortDate(incident.date)}
                      </Td>
                      <Td className="tabular whitespace-nowrap text-xs text-ink-2">
                        {incident.video_time}
                      </Td>
                      <Td className="whitespace-nowrap text-xs text-ink">
                        {incident.camera_id}
                        <div className="truncate text-[10px] text-ink-3">
                          {incident.camera_name}
                        </div>
                      </Td>
                      <Td className="max-w-[180px] truncate text-xs text-ink-2">
                        {incident.location || '—'}
                      </Td>
                      <Td className="whitespace-nowrap text-xs text-ink-2">
                        {incident.violation_type}
                      </Td>
                      <Td className="tabular whitespace-nowrap text-right text-xs font-medium text-ink">
                        {confidencePercent(incident.confidence)}
                      </Td>
                      <Td>
                        <StatusBadge status={incident.status} />
                        {incident.reviewed_at && (
                          <div className="mt-0.5 text-[9px] text-ink-3">
                            {dateTime(incident.reviewed_at)}
                          </div>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-3 py-2">
              <span className="tabular text-[11px] text-ink-3">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of{' '}
                {total.toLocaleString('en-US')}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Previous
                </Button>
                <span className="tabular text-[11px] text-ink-3">
                  Page {page + 1} of {pageCount}
                </span>
                <Button
                  size="sm"
                  disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Panel>
    </>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cx('px-3 py-2 font-semibold', className)}>{children}</th>;
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cx('px-3 py-2 align-middle', className)}>{children}</td>;
}
