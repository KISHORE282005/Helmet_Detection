/** Charts, built as plain SVG against the validated palette.
 *
 *  Every chart here plots a single measure, so identity never rests on colour:
 *  one series blue for the marks, text tokens for all labels, and a hover
 *  layer that reports the exact value. Gridlines are hairline and recessive;
 *  bars are capped at 24px with a 4px rounded data-end.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { cx } from '../ui/primitives';

/** Render charts at true pixel size so strokes stay 2px and dots stay round —
 *  a stretched viewBox would distort both. */
function useMeasuredWidth(fallback = 640) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width;
      if (next > 0) setWidth(next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}

const SERIES = '#3987e5';
const SURFACE = '#0f1520';
const GRID = '#1e2836';
const AXIS = '#2b3849';

/* -------------------------------------------------------------- Tooltip */

function Tooltip({
  x,
  y,
  title,
  value,
  align = 'center',
}: {
  x: number;
  y: number;
  title: string;
  value: string;
  align?: 'center' | 'left' | 'right';
}) {
  const transform =
    align === 'left' ? 'translate(0, -100%)'
    : align === 'right' ? 'translate(-100%, -100%)'
    : 'translate(-50%, -100%)';
  return (
    <div
      className="pointer-events-none absolute z-20 whitespace-nowrap rounded border border-line-strong bg-surface-3 px-2 py-1 shadow-lg"
      style={{ left: x, top: y - 8, transform }}
    >
      <div className="text-[10px] text-ink-3">{title}</div>
      <div className="tabular text-xs font-semibold text-ink">{value}</div>
    </div>
  );
}

/* ----------------------------------------------------------- TrendChart */

export interface TrendPoint {
  date: string;
  count: number;
  label: string;
}

/**
 * Daily violation counts. Area wash + 2px line + an end marker that carries a
 * 2px surface ring so it stays readable where it meets the axis.
 */
export function TrendChart({
  points,
  height = 180,
  unit = 'violations',
}: {
  points: TrendPoint[];
  height?: number;
  unit?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const { ref, width } = useMeasuredWidth();

  const pad = { top: 14, right: 16, bottom: 26, left: 34 };
  const plotW = Math.max(40, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;

  const { max, ticks } = useMemo(() => {
    const peak = Math.max(1, ...points.map((p) => p.count));
    // Round the axis top to a clean number so ticks read 0 / 5 / 10.
    const step = peak <= 4 ? 1 : peak <= 10 ? 2 : Math.ceil(peak / 4 / 5) * 5;
    const top = Math.ceil(peak / step) * step;
    const values: number[] = [];
    for (let v = 0; v <= top; v += step) values.push(v);
    return { max: top, ticks: values };
  }, [points]);

  // All hooks have run by this point, so an early return is safe.
  if (points.length === 0) return null;

  const xAt = (index: number) =>
    pad.left + (points.length === 1 ? plotW / 2 : (index / (points.length - 1)) * plotW);
  const yAt = (value: number) => pad.top + plotH - (value / max) * plotH;

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(p.count)}`).join(' ');
  const area = `${line} L${xAt(points.length - 1)},${pad.top + plotH} L${xAt(0)},${pad.top + plotH} Z`;
  const last = points[points.length - 1];

  // Thin the x labels so they never collide at narrow widths.
  const labelEvery = Math.max(1, Math.ceil(points.length / 8));

  return (
    <div className="relative w-full" ref={ref}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Daily ${unit}, ${points[0].label} to ${last.label}`}
      >
        {ticks.map((value) => (
          <g key={value}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={yAt(value)}
              y2={yAt(value)}
              stroke={value === 0 ? AXIS : GRID}
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <text
              x={pad.left - 7}
              y={yAt(value) + 3}
              textAnchor="end"
              className="tabular"
              fill="#6b7b90"
              fontSize={9}
            >
              {value}
            </text>
          </g>
        ))}

        <path d={area} fill={SERIES} fillOpacity={0.1} />
        <path
          d={line}
          fill="none"
          stroke={SERIES}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />

        {hover !== null && (
          <line
            x1={xAt(hover)}
            x2={xAt(hover)}
            y1={pad.top}
            y2={pad.top + plotH}
            stroke={AXIS}
            strokeWidth={1}
            vectorEffect="non-scaling-stroke"
          />
        )}

        {/* End marker: r=4 (8px) with a 2px surface ring. */}
        <circle
          cx={xAt(points.length - 1)}
          cy={yAt(last.count)}
          r={4}
          fill={SERIES}
          stroke={SURFACE}
          strokeWidth={2}
        />
        {hover !== null && hover !== points.length - 1 && (
          <circle
            cx={xAt(hover)}
            cy={yAt(points[hover].count)}
            r={4}
            fill={SERIES}
            stroke={SURFACE}
            strokeWidth={2}
          />
        )}

        {points.map((p, i) =>
          i % labelEvery === 0 || i === points.length - 1 ? (
            <text
              key={p.date}
              x={xAt(i)}
              y={height - 8}
              textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}
              fill="#6b7b90"
              fontSize={9}
            >
              {p.label}
            </text>
          ) : null,
        )}

        {/* Hit areas are wider than the marks so hovering is forgiving. */}
        {points.map((p, i) => (
          <rect
            key={`hit-${p.date}`}
            x={xAt(i) - plotW / points.length / 2}
            y={pad.top}
            width={plotW / points.length}
            height={plotH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>

      {hover !== null && (
        <Tooltip
          x={xAt(hover)}
          y={yAt(points[hover].count)}
          title={points[hover].label}
          value={`${points[hover].count} ${points[hover].count === 1 ? unit.replace(/s$/, '') : unit}`}
          align={hover === 0 ? 'left' : hover === points.length - 1 ? 'right' : 'center'}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------- BarList */

export interface BarDatum {
  key: string;
  label: string;
  count: number;
  meta?: string;
}

/**
 * Ranked horizontal bars — the form for "which location is worst".
 * Length carries magnitude, so all bars share one colour by design.
 */
export function BarList({
  data,
  unit = 'incidents',
  max: providedMax,
  emphasizeFirst = true,
}: {
  data: BarDatum[];
  unit?: string;
  max?: number;
  emphasizeFirst?: boolean;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const max = providedMax ?? Math.max(1, ...data.map((d) => d.count));

  return (
    <ul className="flex flex-col gap-2.5">
      {data.map((datum, index) => {
        const fraction = datum.count / max;
        const isTop = emphasizeFirst && index === 0;
        return (
          <li
            key={datum.key}
            className="group relative"
            onMouseEnter={() => setHover(datum.key)}
            onMouseLeave={() => setHover(null)}
          >
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="truncate text-xs text-ink" title={datum.label}>
                {datum.label}
              </span>
              <span className="tabular shrink-0 text-xs font-semibold text-ink">
                {datum.count.toLocaleString('en-US')}
              </span>
            </div>
            {/* Track is a lighter step of the surface, not of the series hue,
                so an empty bar never reads as a small value. */}
            <div className="h-2 w-full overflow-hidden rounded-sm bg-surface-3">
              <div
                className="h-full rounded-r-[4px] transition-[width] duration-500"
                style={{
                  width: `${Math.max(fraction * 100, datum.count > 0 ? 2 : 0)}%`,
                  backgroundColor: SERIES,
                  opacity: isTop ? 1 : 0.72,
                }}
              />
            </div>
            {datum.meta && (
              <p className="mt-1 text-[10px] text-ink-3">{datum.meta}</p>
            )}
            {hover === datum.key && (
              <div className="pointer-events-none absolute right-0 -top-1 z-20 -translate-y-full rounded border border-line-strong bg-surface-3 px-2 py-1 shadow-lg">
                <div className="text-[10px] text-ink-3">{datum.label}</div>
                <div className="tabular text-xs font-semibold text-ink">
                  {datum.count.toLocaleString('en-US')} {unit}
                </div>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------ ColumnChart */

/** Compact columns for the hour-of-day distribution. */
export function ColumnChart({
  data,
  height = 130,
  unit = 'incidents',
}: {
  data: BarDatum[];
  height?: number;
  unit?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <div className="relative">
      <div className="flex items-end gap-[2px]" style={{ height }}>
        {data.map((datum, index) => (
          <button
            key={datum.key}
            type="button"
            className="group flex h-full flex-1 cursor-default flex-col justify-end"
            style={{ maxWidth: 24 }}
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(null)}
            aria-label={`${datum.label}: ${datum.count} ${unit}`}
          >
            <div
              className="w-full rounded-t-[4px] transition-all duration-300"
              style={{
                height: `${Math.max((datum.count / max) * 100, datum.count > 0 ? 3 : 1.5)}%`,
                backgroundColor: datum.count > 0 ? SERIES : GRID,
                opacity: hover === null || hover === index ? 1 : 0.55,
              }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1.5 flex gap-[2px] border-t border-line pt-1.5">
        {data.map((datum, index) => (
          <span
            key={datum.key}
            className="flex-1 text-center text-[9px] text-ink-3"
            style={{ maxWidth: 24 }}
          >
            {index % 3 === 0 ? datum.label : ''}
          </span>
        ))}
      </div>
      {hover !== null && (
        <div
          className="pointer-events-none absolute -top-1 z-20 -translate-y-full whitespace-nowrap rounded border border-line-strong bg-surface-3 px-2 py-1 shadow-lg"
          style={{ left: `${((hover + 0.5) / data.length) * 100}%`, transform: 'translate(-50%, -100%)' }}
        >
          <div className="text-[10px] text-ink-3">{data[hover].label}</div>
          <div className="tabular text-xs font-semibold text-ink">
            {data[hover].count} {unit}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- Sparkline */

export function Sparkline({
  values,
  className,
  width = 88,
  height = 24,
}: {
  values: number[];
  className?: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const max = Math.max(1, ...values);
  const xAt = (i: number) => (i / (values.length - 1)) * (width - 4) + 2;
  const yAt = (v: number) => height - 3 - (v / max) * (height - 6);
  const path = values.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(v)}`).join(' ');

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={cx('overflow-visible', className)}
      aria-hidden="true"
    >
      <path d={`${path} L${xAt(values.length - 1)},${height} L${xAt(0)},${height} Z`} fill={SERIES} fillOpacity={0.1} />
      <path d={path} fill="none" stroke={SERIES} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xAt(values.length - 1)} cy={yAt(values[values.length - 1])} r={2.4} fill={SERIES} stroke={SURFACE} strokeWidth={1.5} />
    </svg>
  );
}

/* ----------------------------------------------------------- Ratio meter */

/**
 * The duplicate-suppression story: raw detections vs the incidents they
 * collapsed into. Two labelled marks, never a pie.
 */
export function SuppressionMeter({
  raw,
  unique,
}: {
  raw: number;
  unique: number;
}) {
  const max = Math.max(raw, unique, 1);
  const rows = [
    { label: 'Raw helmet-missing detections', value: raw, opacity: 0.42 },
    { label: 'Unique incidents', value: unique, opacity: 1 },
  ];
  return (
    <div className="flex flex-col gap-3">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3">
            <span className="text-[11px] text-ink-2">{row.label}</span>
            <span className="tabular text-sm font-semibold text-ink">
              {row.value.toLocaleString('en-US')}
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-sm bg-surface-3">
            <div
              className="h-full rounded-r-[4px] transition-[width] duration-700"
              style={{
                width: `${Math.max((row.value / max) * 100, row.value > 0 ? 2 : 0)}%`,
                backgroundColor: SERIES,
                opacity: row.opacity,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
