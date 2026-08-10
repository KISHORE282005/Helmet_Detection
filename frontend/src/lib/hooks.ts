/** React Query bindings. Poll intervals are deliberate: safety-critical data
 *  refreshes often, reference data rarely. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { api } from './api';
import type {
  AnalysisJob,
  AnalyticsResponse,
  Camera,
  CameraList,
  DashboardSummary,
  Incident,
  IncidentFilterOptions,
  IncidentPage,
  IncidentStatus,
  ModelsResponse,
  NotificationFeed,
  SafetyReport,
  SettingsResponse,
  SystemHealth,
  Upload,
} from './types';

export const REFRESH = {
  /** Anything an operator is watching for a violation to appear. */
  live: 5_000,
  /** Analysis progress — the pipeline emits every 10 analyzed frames. */
  progress: 1_000,
  /** Reference and aggregate data. */
  slow: 60_000,
} as const;

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardSummary>('/api/dashboard/summary'),
    refetchInterval: REFRESH.live,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<SystemHealth>('/api/system/health'),
    refetchInterval: REFRESH.live * 2,
  });
}

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<NotificationFeed>('/api/system/notifications'),
    refetchInterval: REFRESH.live,
  });
}

export function useCameras() {
  return useQuery({
    queryKey: ['cameras'],
    queryFn: () => api.get<CameraList>('/api/cameras'),
    refetchInterval: REFRESH.live * 2,
  });
}

export type IncidentQuery = {
  camera_id?: string;
  location?: string;
  status?: string;
  violation_type?: string;
  date_from?: string;
  date_to?: string;
  min_confidence?: number;
  search?: string;
  analysis_id?: string;
  limit?: number;
  offset?: number;
  order_by?: string;
  direction?: string;
};

export function useIncidents(query: IncidentQuery, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: ['incidents', query],
    queryFn: () => api.get<IncidentPage>('/api/incidents', query),
    refetchInterval: options?.refetchInterval,
    placeholderData: (previous) => previous,
  });
}

export function useIncident(incidentId: string | undefined) {
  return useQuery({
    queryKey: ['incident', incidentId],
    queryFn: () => api.get<Incident>(`/api/incidents/${incidentId}`),
    enabled: Boolean(incidentId),
  });
}

export function useIncidentFilters() {
  return useQuery({
    queryKey: ['incident-filters'],
    queryFn: () => api.get<IncidentFilterOptions>('/api/incidents/filters'),
    staleTime: REFRESH.slow,
  });
}

export function useReviewIncident() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      incidentId: string;
      status: IncidentStatus;
      reviewed_by?: string;
      remarks?: string;
    }) =>
      api.patch<Incident>(`/api/incidents/${input.incidentId}`, {
        status: input.status,
        reviewed_by: input.reviewed_by ?? 'Supervisor',
        remarks: input.remarks,
      }),
    onSuccess: (incident) => {
      client.setQueryData(['incident', incident.incident_id], incident);
      // Review changes ripple into every count on the dashboard.
      void client.invalidateQueries({ queryKey: ['incidents'] });
      void client.invalidateQueries({ queryKey: ['dashboard'] });
      void client.invalidateQueries({ queryKey: ['notifications'] });
      void client.invalidateQueries({ queryKey: ['analytics'] });
      void client.invalidateQueries({ queryKey: ['reports'] });
    },
  });
}

export function useAnalytics(range: string, custom?: { from: string; to: string }) {
  return useQuery({
    queryKey: ['analytics', range, custom],
    queryFn: () =>
      api.get<AnalyticsResponse>('/api/analytics', {
        range,
        date_from: custom?.from,
        date_to: custom?.to,
      }),
    refetchInterval: REFRESH.slow,
  });
}

export function useReportSummary() {
  return useQuery({
    queryKey: ['reports', 'summary'],
    queryFn: () => api.get<{ reports: SafetyReport[] }>('/api/reports/summary'),
    refetchInterval: REFRESH.slow,
  });
}

export function useReport(period: string, enabled = true) {
  return useQuery({
    queryKey: ['reports', period],
    queryFn: () => api.get<SafetyReport>(`/api/reports/${period}`),
    enabled,
  });
}

export function useAnalysisJobs() {
  return useQuery({
    queryKey: ['analysis-jobs'],
    queryFn: () => api.get<{ items: AnalysisJob[]; active_job_id: string | null }>('/api/analysis'),
    refetchInterval: (query) => {
      const active = query.state.data?.items.some(
        (job) => job.status === 'running' || job.status === 'queued',
      );
      return active ? REFRESH.progress : REFRESH.slow;
    },
  });
}

/** Polls fast while the job runs, then stops — no wasted requests once done. */
export function useAnalysisJob(jobId: string | null) {
  return useQuery({
    queryKey: ['analysis-job', jobId],
    queryFn: () => api.get<AnalysisJob>(`/api/analysis/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'queued' ? REFRESH.progress : false;
    },
  });
}

export function useUploads() {
  return useQuery({
    queryKey: ['uploads'],
    queryFn: () => api.get<{ items: Upload[] }>('/api/analysis/uploads'),
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<SettingsResponse>('/api/settings'),
  });
}

export function useUpdateSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, number | boolean>) =>
      api.patch<{ values: Record<string, number | boolean> }>('/api/settings', values),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['settings'] });
    },
  });
}

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => api.get<ModelsResponse>('/api/settings/models'),
    refetchInterval: REFRESH.slow,
  });
}

export function useCameraMutations() {
  const client = useQueryClient();
  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ['cameras'] });
    void client.invalidateQueries({ queryKey: ['dashboard'] });
    void client.invalidateQueries({ queryKey: ['health'] });
  };

  return {
    save: useMutation({
      mutationFn: (input: { camera: Partial<Camera>; isNew: boolean }) =>
        input.isNew
          ? api.post<Camera>('/api/cameras', input.camera)
          : api.put<Camera>(`/api/cameras/${input.camera.camera_id}`, input.camera),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (cameraId: string) => api.delete<void>(`/api/cameras/${cameraId}`),
      onSuccess: invalidate,
    }),
    test: useMutation({
      mutationFn: (cameraId: string) =>
        api.post<{ camera_id: string; stream_status: string; message: string }>(
          `/api/cameras/${cameraId}/test`,
        ),
      onSuccess: invalidate,
    }),
    toggleAi: useMutation({
      mutationFn: (input: { cameraId: string; enabled: boolean }) =>
        api.post<Camera>(`/api/cameras/${input.cameraId}/ai`, { enabled: input.enabled }),
      onSuccess: invalidate,
    }),
    refresh: useMutation({
      mutationFn: () => api.post<CameraList>('/api/cameras/refresh'),
      onSuccess: invalidate,
    }),
  };
}

/** Escape hatch for one-off queries that don't warrant a named hook. */
export function useApi<T>(
  key: unknown[],
  path: string,
  params?: Record<string, unknown>,
  options?: Partial<UseQueryOptions<T>>,
) {
  return useQuery({
    queryKey: key,
    queryFn: () => api.get<T>(path, params),
    ...options,
  } as UseQueryOptions<T>);
}
