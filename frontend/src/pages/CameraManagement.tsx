/** Camera master data.
 *
 *  Credentials are never entered or shown here: the backend stores an IP and
 *  a port for reachability checks only, and the UI reports connection state
 *  rather than a stream URL.
 */

import { useState } from 'react';
import { PageHeader } from '../components/layout/AppShell';
import { streamLabel, streamTone } from '../components/domain/CameraTile';
import {
  Badge,
  Button,
  CameraIcon,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  Panel,
  RefreshIcon,
  Select,
  Skeleton,
  StatusDot,
  TextInput,
  Toggle,
  cx,
} from '../components/ui/primitives';
import { useCameraMutations, useCameras } from '../lib/hooks';
import { dateTime, relativeTime } from '../lib/format';
import type { Camera } from '../lib/types';

const BLANK: Partial<Camera> = {
  camera_id: '',
  camera_name: '',
  department: '',
  area: '',
  location: '',
  ip_address: '',
  rtsp_port: 554,
  rtsp_channel: '',
  supervisor_id: '',
  status: 'Active',
  ai_enabled: true,
  target_fps: 10,
};

export default function CameraManagement() {
  const { data, isLoading, isError, error, refetch } = useCameras();
  const { save, remove, test, toggleAi, refresh } = useCameraMutations();

  const [editing, setEditing] = useState<Partial<Camera> | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [testResult, setTestResult] = useState<{ id: string; message: string; ok: boolean } | null>(
    null,
  );

  const openNew = () => {
    setEditing({ ...BLANK });
    setIsNew(true);
  };

  const openEdit = (camera: Camera) => {
    setEditing({ ...camera });
    setIsNew(false);
  };

  const runTest = async (cameraId: string) => {
    const result = await test.mutateAsync(cameraId);
    setTestResult({
      id: cameraId,
      message: result.message,
      ok: result.stream_status === 'online',
    });
  };

  if (isError) {
    return (
      <>
        <PageHeader title="Cameras" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const cameras = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Camera Management"
        subtitle="Hikvision camera registry, AI assignment and connection state"
        actions={
          <>
            <Button size="sm" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
              <RefreshIcon className={cx('h-3.5 w-3.5', refresh.isPending && 'animate-spin')} />
              Test all
            </Button>
            <Button size="sm" variant="primary" onClick={openNew}>
              Add camera
            </Button>
          </>
        }
      />

      <div className="mb-3 rounded-lg border border-line bg-surface px-3 py-2 text-[11px] leading-relaxed text-ink-3">
        RTSP usernames and passwords are never stored or displayed by the dashboard.
        A connection test opens a TCP connection to the camera's RTSP port and reports
        only whether it answered.
      </div>

      {testResult && (
        <div
          className={cx(
            'mb-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-[11px]',
            testResult.ok
              ? 'border-good/35 bg-good/8 text-good'
              : 'border-critical/40 bg-critical/8 text-critical',
          )}
        >
          <StatusDot tone={testResult.ok ? 'good' : 'critical'} />
          <span className="font-semibold">{testResult.id}</span>
          <span className="text-ink-2">{testResult.message}</span>
          <button
            type="button"
            className="ml-auto text-ink-3 hover:text-ink"
            onClick={() => setTestResult(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <Panel dense>
        {isLoading ? (
          <div className="flex flex-col gap-2 p-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : cameras.length === 0 ? (
          <EmptyState
            icon={<CameraIcon className="h-7 w-7" />}
            title="No cameras registered"
            description="Register a camera to track its connection state and attribute incidents to a location."
            action={
              <Button size="sm" variant="primary" onClick={openNew}>
                Add the first camera
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left">
              <thead>
                <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-3">
                  <th className="px-3 py-2">Camera ID</th>
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Location</th>
                  <th className="px-3 py-2">IP address</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">AI</th>
                  <th className="px-3 py-2 text-right">Target FPS</th>
                  <th className="px-3 py-2 text-right">Today</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map((camera) => {
                  const tone = streamTone(camera);
                  return (
                    <tr
                      key={camera.camera_id}
                      className="border-b border-line transition-colors last:border-0 hover:bg-surface-2"
                    >
                      <td className="tabular px-3 py-2 text-xs font-semibold text-ink">
                        {camera.camera_id}
                      </td>
                      <td className="px-3 py-2 text-xs text-ink-2">
                        {camera.camera_name}
                        <div className="text-[10px] text-ink-3">{camera.department || '—'}</div>
                      </td>
                      <td className="px-3 py-2 text-xs text-ink-2">
                        {camera.location || camera.area || '—'}
                      </td>
                      <td className="tabular px-3 py-2 text-xs text-ink-2">
                        {camera.ip_address || <span className="text-ink-3">not set</span>}
                        {camera.ip_address && (
                          <div className="text-[10px] text-ink-3">port {camera.rtsp_port}</div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <StatusDot
                          tone={tone}
                          pulse={camera.stream_status === 'online'}
                          label={
                            <span
                              className={cx(
                                'text-[10px] font-semibold',
                                tone === 'good' && 'text-good',
                                tone === 'critical' && 'text-critical',
                                tone === 'neutral' && 'text-ink-3',
                              )}
                            >
                              {streamLabel(camera)}
                            </span>
                          }
                        />
                        {camera.last_seen && (
                          <div
                            className="mt-0.5 text-[10px] text-ink-3"
                            title={dateTime(camera.last_seen)}
                          >
                            seen {relativeTime(camera.last_seen)}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Toggle
                          checked={camera.ai_enabled}
                          onChange={(enabled) =>
                            toggleAi.mutate({ cameraId: camera.camera_id, enabled })
                          }
                          label={`AI processing for ${camera.camera_id}`}
                        />
                      </td>
                      <td className="tabular px-3 py-2 text-right text-xs text-ink-2">
                        {camera.target_fps || '—'}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {camera.violations_today > 0 ? (
                          <Badge tone="critical">{camera.violations_today}</Badge>
                        ) : (
                          <span className="text-xs text-ink-3">0</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            size="sm"
                            onClick={() => void runTest(camera.camera_id)}
                            disabled={test.isPending}
                          >
                            Test
                          </Button>
                          <Button size="sm" onClick={() => openEdit(camera)}>
                            Configure
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <CameraForm
        camera={editing}
        isNew={isNew}
        supervisors={data?.supervisors ?? []}
        saving={save.isPending}
        error={save.error}
        onClose={() => setEditing(null)}
        onSave={async (camera) => {
          await save.mutateAsync({ camera, isNew });
          setEditing(null);
        }}
        onDelete={
          isNew
            ? undefined
            : async (cameraId) => {
                await remove.mutateAsync(cameraId);
                setEditing(null);
              }
        }
      />
    </>
  );
}

function CameraForm({
  camera,
  isNew,
  supervisors,
  saving,
  error,
  onClose,
  onSave,
  onDelete,
}: {
  camera: Partial<Camera> | null;
  isNew: boolean;
  supervisors: { supervisor_id: string; supervisor_name: string }[];
  saving: boolean;
  error: unknown;
  onClose: () => void;
  onSave: (camera: Partial<Camera>) => Promise<void>;
  onDelete?: (cameraId: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Partial<Camera>>(camera ?? BLANK);
  const [dirtyKey, setDirtyKey] = useState<string | null>(null);

  // Re-seed the form when a different camera is opened.
  if (camera && camera.camera_id !== dirtyKey) {
    setDraft({ ...camera });
    setDirtyKey(camera.camera_id ?? '');
  }

  const set = (patch: Partial<Camera>) => setDraft((current) => ({ ...current, ...patch }));

  return (
    <Modal
      open={camera !== null}
      onClose={onClose}
      title={isNew ? 'Add camera' : `Configure ${camera?.camera_id}`}
      subtitle="Connection details are used for reachability checks and incident attribution"
      width="max-w-2xl"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Camera ID" hint={isNew ? 'Unique, e.g. CAM004' : 'Cannot be changed'}>
          <TextInput
            value={draft.camera_id ?? ''}
            disabled={!isNew}
            onChange={(event) => set({ camera_id: event.target.value.toUpperCase() })}
            placeholder="CAM004"
          />
        </Field>
        <Field label="Camera name">
          <TextInput
            value={draft.camera_name ?? ''}
            onChange={(event) => set({ camera_name: event.target.value })}
            placeholder="Assembly Line 3"
          />
        </Field>
        <Field label="Department">
          <TextInput
            value={draft.department ?? ''}
            onChange={(event) => set({ department: event.target.value })}
            placeholder="Assembly"
          />
        </Field>
        <Field label="Area">
          <TextInput
            value={draft.area ?? ''}
            onChange={(event) => set({ area: event.target.value })}
            placeholder="Stage 3"
          />
        </Field>
        <Field label="Location" className="sm:col-span-2" hint="Shown on incidents and reports">
          <TextInput
            value={draft.location ?? ''}
            onChange={(event) => set({ location: event.target.value })}
            placeholder="Production Area A"
          />
        </Field>
        <Field label="IP address" hint="Used only for the reachability check">
          <TextInput
            value={draft.ip_address ?? ''}
            onChange={(event) => set({ ip_address: event.target.value })}
            placeholder="192.168.1.64"
          />
        </Field>
        <Field label="RTSP port">
          <TextInput
            type="number"
            value={draft.rtsp_port ?? 554}
            onChange={(event) => set({ rtsp_port: Number(event.target.value) })}
          />
        </Field>
        <Field label="Stream channel" hint="Optional Hikvision channel path, e.g. 101">
          <TextInput
            value={draft.rtsp_channel ?? ''}
            onChange={(event) => set({ rtsp_channel: event.target.value })}
            placeholder="101"
          />
        </Field>
        <Field label="Target FPS" hint="Frames per second to process in Phase 2">
          <TextInput
            type="number"
            value={draft.target_fps ?? 0}
            onChange={(event) => set({ target_fps: Number(event.target.value) })}
          />
        </Field>
        <Field label="Supervisor" hint="Receives the alert email for this camera">
          <Select
            value={draft.supervisor_id ?? ''}
            onChange={(event) => set({ supervisor_id: event.target.value })}
          >
            <option value="">Unassigned</option>
            {supervisors.map((supervisor) => (
              <option key={supervisor.supervisor_id} value={supervisor.supervisor_id}>
                {supervisor.supervisor_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Registry status">
          <Select
            value={draft.status ?? 'Active'}
            onChange={(event) => set({ status: event.target.value })}
          >
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </Select>
        </Field>

        <div className="flex items-center justify-between gap-3 rounded border border-line bg-surface-2 px-3 py-2 sm:col-span-2">
          <div>
            <p className="text-xs font-medium text-ink">AI processing</p>
            <p className="text-[10px] text-ink-3">
              When off, footage from this camera is stored but not analysed.
            </p>
          </div>
          <Toggle
            checked={draft.ai_enabled ?? true}
            onChange={(enabled) => set({ ai_enabled: enabled })}
            label="AI processing"
          />
        </div>
      </div>

      {error != null && (
        <p className="mt-3 text-[11px] text-critical">
          {error instanceof Error ? error.message : 'Could not save the camera'}
        </p>
      )}

      <div className="mt-4 flex items-center gap-2 border-t border-line pt-3">
        {onDelete && draft.camera_id && (
          <Button
            variant="danger"
            size="sm"
            onClick={() => void onDelete(draft.camera_id!)}
          >
            Remove camera
          </Button>
        )}
        <div className="ml-auto flex gap-2">
          <Button size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            variant="primary"
            disabled={saving || !draft.camera_id || !draft.camera_name}
            onClick={() => void onSave(draft)}
          >
            {saving ? 'Saving…' : isNew ? 'Add camera' : 'Save changes'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
