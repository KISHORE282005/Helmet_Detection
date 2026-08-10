/** Wire types mirroring api/schemas.py and the router responses. */

export type StreamStatus = 'online' | 'offline' | 'unconfigured' | 'unknown';
export type IncidentStatus = 'Open' | 'Confirmed' | 'False Positive' | 'Resolved';

export interface Incident {
  incident_id: string;
  camera_id: string;
  camera_name: string;
  location: string;
  video_name: string;
  /** Offset inside the source clip (HH:MM:SS). */
  video_time: string;
  date: string;
  /** ISO timestamp of when the pipeline wrote the record. */
  detected_at: string;
  violation_type: string;
  confidence: number;
  track_id: number;
  status: IncidentStatus;
  scene_persons: number;
  scene_helmet: number;
  scene_no_helmet: number;
  confirm_frames: number;
  analysis_id: string;
  reviewed_at: string;
  reviewed_by: string;
  remarks: string;
  evidence: string | null;
  poster: string | null;
  related?: Incident[];
}

export interface IncidentPage {
  items: Incident[];
  total: number;
  limit: number;
  offset: number;
}

export interface IncidentFilterOptions {
  cameras: string[];
  locations: string[];
  statuses: IncidentStatus[];
  violation_types: string[];
  videos: string[];
}

export interface Camera {
  camera_id: string;
  camera_name: string;
  department: string;
  area: string;
  location: string;
  ip_address: string;
  rtsp_port: number;
  rtsp_channel: string;
  supervisor_id: string;
  status: string;
  stream_status: StreamStatus;
  ai_enabled: boolean;
  target_fps: number;
  last_seen: string;
  source: string;
  fps: number;
  violations_today: number;
}

export interface Supervisor {
  supervisor_id: string;
  supervisor_name: string;
  department: string;
  email: string;
  status: string;
}

export interface CameraList {
  items: Camera[];
  last_poll: string | null;
  poll_interval_seconds: number;
  supervisors: Supervisor[];
}

export interface GroupCount {
  key: string;
  count: number;
  avg_confidence?: number;
}

export interface DashboardSummary {
  generated_at: string | null;
  cameras: {
    total: number;
    online: number;
    offline: number;
    unconfigured: number;
    last_poll: string | null;
  };
  active_violations: { count: number; requires_attention: boolean };
  today: {
    violations: number;
    previous: number;
    delta_percent: number | null;
    raw_detections: number;
    people_detected: number;
  };
  compliance: {
    rate: number | null;
    delta: number | null;
    people_detected: number;
    basis: string;
  };
  week: {
    violations: number;
    people_detected: number;
    compliance: number | null;
    trend: GroupCount[];
  };
  open_incidents: Incident[];
  latest_incidents: Incident[];
  camera_status: Camera[];
  top_locations: GroupCount[];
}

export interface HealthComponent {
  name: string;
  status: 'online' | 'offline' | 'degraded';
  detail: string;
}

export interface SystemHealth {
  phase: number;
  mode: 'recorded' | 'live';
  server_time: string;
  uptime_seconds: number;
  components: HealthComponent[];
  healthy: boolean;
  camera_poll: { last_poll: string | null; interval_seconds: number };
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  camera_id: string;
  camera_name: string;
  location: string;
  video_time: string;
  detected_at: string;
  confidence: number;
  evidence: string | null;
}

export interface NotificationFeed {
  items: NotificationItem[];
  unread: number;
  today: number;
  channels: { name: string; status: string }[];
}

export interface Upload {
  upload_id: string;
  filename: string;
  stored_name: string;
  size_bytes: number;
  uploaded_at: string;
  fps: number;
  total_frames: number;
  width: number;
  height: number;
  duration_seconds: number;
  resolution: string;
}

export interface AnalysisProgress {
  frames_total: number;
  frames_read: number;
  frames_analyzed: number;
  progress: number;
  people_detected: number;
  person_frames: number;
  raw_detections: number;
  compliant_frames: number;
  incidents: number;
  processing_fps: number;
  elapsed_seconds: number;
}

export interface AnalysisResult {
  video_name: string;
  total_frames: number;
  frames_analyzed: number;
  video_fps: number;
  people_detected: number;
  person_frames: number;
  compliant_frames: number;
  raw_detections: number;
  unique_incidents: number;
  elapsed_seconds: number;
  processing_fps: number;
  incident_ids: string[];
  report_available: boolean;
  report_name: string | null;
  frame_skip: number;
}

export interface AnalysisJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  video: {
    upload_id: string;
    filename: string;
    size_bytes: number;
    duration_seconds: number;
    resolution: string;
    fps: number;
    total_frames: number;
  };
  camera: { camera_id?: string | null; camera_name?: string | null; location?: string | null };
  progress: AnalysisProgress;
  result: AnalysisResult | null;
}

export interface AnalyticsResponse {
  range: { from: string; to: string; key: string };
  totals: {
    incidents: number;
    raw_detections: number;
    people_detected: number;
    person_frames: number;
    frames_analyzed: number;
    runs: number;
    avg_confidence: number;
    compliance_rate: number | null;
    suppressed_duplicates: number;
  };
  trend: { date: string; count: number }[];
  by_camera: GroupCount[];
  by_location: GroupCount[];
  by_status: GroupCount[];
  by_hour: GroupCount[];
  recent_runs: AnalysisRun[];
}

export interface AnalysisRun {
  run_id: string;
  video_name: string;
  camera_id: string;
  camera_name: string;
  location: string;
  date: string;
  finished_at: string;
  frames_analyzed: number;
  people_detected: number;
  raw_detections: number;
  unique_incidents: number;
  elapsed_seconds: number;
  processing_fps: number;
  status: string;
}

export interface SafetyReport {
  period: 'daily' | 'weekly' | 'monthly';
  range: { from: string; to: string };
  label: string;
  totals: {
    violations: number;
    raw_detections: number;
    people_detected: number;
    analysis_runs: number;
    compliance_rate: number | null;
    avg_confidence: number;
  };
  worst_camera: GroupCount | null;
  worst_location: GroupCount | null;
  by_camera: GroupCount[];
  by_location: GroupCount[];
  by_status: GroupCount[];
  trend: GroupCount[];
  has_data: boolean;
  incidents?: Incident[];
}

export interface SettingsField {
  key: string;
  label: string;
  type: 'ratio' | 'int' | 'bool';
  min?: number;
  max?: number;
  step?: number;
  help: string;
}

export interface SettingsGroup {
  id: string;
  title: string;
  description: string;
  fields: SettingsField[];
}

export interface SettingsResponse {
  groups: SettingsGroup[];
  values: Record<string, number | boolean>;
  notes: { one_incident_per_track: boolean; scope: string };
}

export interface ModelInfo {
  role: string;
  name: string;
  framework: string;
  status: 'available' | 'missing' | 'fallback' | 'planned';
  size_mb: number | null;
  phase: number;
  note?: string | null;
}

export interface ModelsResponse {
  engine: { loaded: boolean; error: string | null; detail: string };
  models: ModelInfo[];
  employee_recognition: {
    enabled: boolean;
    status: string;
    components: string[];
    note: string;
  };
}
