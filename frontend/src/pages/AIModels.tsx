/** Model inventory and the Phase 2 recognition roadmap. */

import { PageHeader } from '../components/layout/AppShell';
import {
  Badge,
  ErrorState,
  Panel,
  Skeleton,
  StatusDot,
  cx,
  type Tone,
} from '../components/ui/primitives';
import { useHealth, useModels } from '../lib/hooks';
import type { ModelInfo } from '../lib/types';

const STATUS_TONE: Record<ModelInfo['status'], Tone> = {
  available: 'good',
  fallback: 'warning',
  missing: 'critical',
  planned: 'accent',
};

const STATUS_LABEL: Record<ModelInfo['status'], string> = {
  available: 'Loaded',
  fallback: 'Fallback',
  missing: 'Missing',
  planned: 'Phase 2',
};

export default function AIModels() {
  const { data, isLoading, isError, error, refetch } = useModels();
  const health = useHealth();

  if (isError) {
    return (
      <>
        <PageHeader title="AI Models" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const phase1 = data?.models.filter((model) => model.phase === 1) ?? [];
  const phase2 = data?.models.filter((model) => model.phase === 2) ?? [];

  return (
    <>
      <PageHeader
        title="AI Models"
        subtitle="The detection stack running the safety pipeline"
        actions={
          data && (
            <Badge tone={data.engine.loaded ? 'good' : 'neutral'}>
              {data.engine.loaded ? 'Engine loaded' : 'Engine idle'}
            </Badge>
          )
        }
      />

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="flex flex-col gap-4 xl:col-span-2">
            <Panel eyebrow="Detection" title="Active detection stack" dense>
              <ul className="divide-y divide-line">
                {phase1.map((model) => (
                  <ModelRow key={model.role} model={model} />
                ))}
              </ul>
            </Panel>

            <Panel eyebrow="Phase 2" title="Employee Recognition">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge tone="accent">{data?.employee_recognition.status}</Badge>
                <span className="text-[11px] text-ink-3">
                  Disabled in this build
                </span>
              </div>
              <p className="mb-3 text-[11px] leading-relaxed text-ink-3">
                {data?.employee_recognition.note}
              </p>
              <ul className="divide-y divide-line">
                {phase2.map((model) => (
                  <ModelRow key={model.role} model={model} />
                ))}
              </ul>
            </Panel>
          </div>

          <div className="flex flex-col gap-4">
            <Panel eyebrow="Engine" title="Runtime state">
              <p className="text-[11px] leading-relaxed text-ink-3">{data?.engine.detail}</p>
              {data?.engine.error && (
                <p className="mt-2 rounded border border-critical/40 bg-critical/8 px-2 py-1.5 text-[11px] text-critical">
                  {data.engine.error}
                </p>
              )}
              <ul className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
                {(health.data?.components ?? []).map((component) => (
                  <li
                    key={component.name}
                    className="flex items-start justify-between gap-2 text-[11px]"
                  >
                    <StatusDot
                      tone={
                        component.status === 'online'
                          ? 'good'
                          : component.status === 'degraded'
                            ? 'warning'
                            : 'critical'
                      }
                      size="sm"
                      label={<span className="text-ink-2">{component.name}</span>}
                    />
                    <span
                      className={cx(
                        'shrink-0 text-[10px] font-semibold uppercase',
                        component.status === 'online' && 'text-good',
                        component.status === 'degraded' && 'text-warning',
                        component.status === 'offline' && 'text-critical',
                      )}
                    >
                      {component.status}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel eyebrow="Architecture" title="Processing path">
              <ol className="flex flex-col gap-0">
                {[
                  ['Camera', 'Hikvision IP camera', 2],
                  ['Transport', 'RTSP stream', 2],
                  ['Detection', 'YOLO11 person detection', 1],
                  ['Tracking', 'ByteTrack identity assignment', 1],
                  ['Verification', 'Consecutive-frame confirmation', 1],
                  ['Incident manager', 'One record per track', 1],
                  ['Recognition', 'InsightFace attribution', 2],
                  ['Storage', 'SQLite — PostgreSQL in production', 1],
                  ['Dashboard', 'SafeVision AI', 1],
                ].map(([stage, detail, phase], index, all) => (
                  <li key={stage as string} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <span
                        className={cx(
                          'mt-1 h-2 w-2 shrink-0 rounded-full',
                          phase === 1 ? 'bg-accent' : 'bg-ink-3',
                        )}
                      />
                      {index < all.length - 1 && <span className="w-px flex-1 bg-line-strong" />}
                    </div>
                    <div className={cx('min-w-0 flex-1', index < all.length - 1 && 'pb-2.5')}>
                      <div className="flex items-center gap-1.5">
                        <p className="text-xs font-medium text-ink">{stage}</p>
                        {phase === 2 && (
                          <span className="text-[9px] font-semibold uppercase text-ink-3">
                            Phase 2
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-ink-3">{detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}

function ModelRow({ model }: { model: ModelInfo }) {
  return (
    <li className="flex items-start justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-ink">{model.name}</span>
          <span className="text-[10px] text-ink-3">{model.role}</span>
        </div>
        <p className="mt-0.5 text-[11px] text-ink-3">{model.framework}</p>
        {model.note && (
          <p className="mt-1 text-[11px] text-warning">{model.note}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {model.size_mb && (
          <span className="tabular text-[10px] text-ink-3">{model.size_mb} MB</span>
        )}
        <Badge tone={STATUS_TONE[model.status]}>{STATUS_LABEL[model.status]}</Badge>
      </div>
    </li>
  );
}
