/** Display formatting. Anything the operator reads passes through here so
 *  units, precision and "no data" wording stay consistent across pages. */

export const DASH = '—';

export function compactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString('en-US');
}

/** Two-digit padding for counts the design shows as "04". */
export function padded(value: number | null | undefined, width = 2): string {
  if (value === null || value === undefined) return DASH;
  return String(value).padStart(width, '0');
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  return `${value.toFixed(digits)}%`;
}

export function confidencePercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  return `${Math.round(value * 100)}%`;
}

export function signedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

export function bytes(value: number | null | undefined): string {
  if (!value) return DASH;
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

/** Seconds as MM:SS, or HH:MM:SS past an hour. */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return DASH;
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function clockTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return DASH;
  return date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

export function shortDate(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return DASH;
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function dateTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return DASH;
  return `${shortDate(iso)} ${clockTime(iso)}`;
}

/** "4m ago" — used where recency matters more than the exact instant. */
export function relativeTime(iso: string | null | undefined): string {
  const date = parse(iso);
  if (!date) return DASH;
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function isoDay(offsetDays = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

export function labelDay(iso: string): string {
  const date = parse(iso);
  if (!date) return iso;
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
}
