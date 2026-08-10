/** Detection, tracking and incident configuration. */

import { useEffect, useState } from 'react';
import { PageHeader } from '../components/layout/AppShell';
import {
  Badge,
  Button,
  ErrorState,
  Panel,
  Skeleton,
  TextInput,
  Toggle,
  cx,
} from '../components/ui/primitives';
import { useSettings, useUpdateSettings } from '../lib/hooks';
import type { SettingsField } from '../lib/types';

type Values = Record<string, number | boolean>;

export default function Settings() {
  const { data, isLoading, isError, error, refetch } = useSettings();
  const update = useUpdateSettings();
  const [draft, setDraft] = useState<Values>({});

  // Seed the form once the server values arrive, and after every save.
  useEffect(() => {
    if (data?.values) setDraft(data.values);
  }, [data?.values]);

  if (isError) {
    return (
      <>
        <PageHeader title="Settings" />
        <Panel>
          <ErrorState error={error} onRetry={() => void refetch()} />
        </Panel>
      </>
    );
  }

  const dirty =
    data?.values &&
    Object.keys(draft).some((key) => draft[key] !== data.values[key]);

  return (
    <>
      <PageHeader
        title="AI Configuration"
        subtitle="Detection thresholds, tracking behaviour and incident rules"
        actions={
          <>
            {dirty && <Badge tone="warning">Unsaved changes</Badge>}
            <Button
              size="sm"
              disabled={!dirty}
              onClick={() => data?.values && setDraft(data.values)}
            >
              Reset
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={!dirty || update.isPending}
              onClick={() => update.mutate(draft)}
            >
              {update.isPending ? 'Applying…' : 'Apply settings'}
            </Button>
          </>
        }
      />

      {data && (
        <div className="mb-4 rounded-lg border border-line bg-surface px-3 py-2 text-[11px] leading-relaxed text-ink-3">
          {data.notes.scope}
        </div>
      )}

      {update.isSuccess && (
        <div className="mb-4 rounded-lg border border-good/35 bg-good/8 px-3 py-2 text-[11px] text-good">
          Settings applied. They take effect on the next analysis run.
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-56 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {data?.groups.map((group) => (
            <Panel key={group.id} eyebrow={group.id} title={group.title}>
              <p className="mb-3 text-[11px] text-ink-3">{group.description}</p>
              <div className="flex flex-col divide-y divide-line">
                {group.fields.map((field) => (
                  <SettingRow
                    key={field.key}
                    field={field}
                    value={draft[field.key]}
                    onChange={(value) =>
                      setDraft((current) => ({ ...current, [field.key]: value }))
                    }
                  />
                ))}
              </div>
            </Panel>
          ))}

          {/* Stated as a fixed rule, because the pipeline enforces it. */}
          <Panel eyebrow="incidents" title="Duplicate prevention">
            <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
              <div>
                <p className="text-xs font-medium text-ink">One incident per track</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-ink-3">
                  A tracked person can raise a violation once. If the same worker appears
                  without a helmet across 500 frames, the system records one incident,
                  not 500. This is enforced by the tracker and is not configurable.
                </p>
              </div>
              <Badge tone="good">Always on</Badge>
            </div>
            <div className="flex items-start justify-between gap-3 pt-3">
              <div>
                <p className="text-xs font-medium text-ink">Best evidence selection</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-ink-3">
                  Among the frames of a confirmed run, the saved image is the one scoring
                  highest on subject size, sharpness and helmet confidence.
                </p>
              </div>
              <Badge tone="good">Always on</Badge>
            </div>
          </Panel>
        </div>
      )}

      {update.isError && (
        <p className="mt-3 text-[11px] text-critical">
          {update.error instanceof Error ? update.error.message : 'Could not apply the settings'}
        </p>
      )}
    </>
  );
}

function SettingRow({
  field,
  value,
  onChange,
}: {
  field: SettingsField;
  value: number | boolean | undefined;
  onChange: (value: number | boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0 flex-1">
        <label className="text-xs font-medium text-ink" htmlFor={field.key}>
          {field.label}
        </label>
        <p className="mt-0.5 text-[11px] leading-relaxed text-ink-3">{field.help}</p>
      </div>

      <div className="w-40 shrink-0">
        {field.type === 'bool' ? (
          <div className="flex justify-end pt-0.5">
            <Toggle
              checked={Boolean(value)}
              onChange={onChange}
              label={field.label}
            />
          </div>
        ) : field.type === 'ratio' ? (
          <div className="flex items-center gap-2">
            <input
              id={field.key}
              type="range"
              min={field.min}
              max={field.max}
              step={field.step ?? 0.01}
              value={Number(value ?? 0)}
              onChange={(event) => onChange(Number(event.target.value))}
              className="h-1 w-full cursor-pointer appearance-none rounded-full bg-surface-3 accent-[#3987e5]"
            />
            <span className="tabular w-10 shrink-0 text-right text-xs font-semibold text-ink">
              {Number(value ?? 0).toFixed(2)}
            </span>
          </div>
        ) : (
          <TextInput
            id={field.key}
            type="number"
            min={field.min}
            max={field.max}
            step={field.step ?? 1}
            value={Number(value ?? 0)}
            onChange={(event) => onChange(Number(event.target.value))}
            className={cx('text-right')}
          />
        )}
      </div>
    </div>
  );
}
