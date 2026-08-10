/** Shared building blocks: panels, status marks, badges, buttons, states.
 *
 *  Status colour is never the only signal — every StatusDot and Badge carries
 *  a text label beside it, so the meaning survives colour-blind vision and a
 *  washed-out control-room monitor.
 */

import type { ReactNode } from 'react';

export function cx(...values: (string | false | null | undefined)[]) {
  return values.filter(Boolean).join(' ');
}

/* ------------------------------------------------------------------ Panel */

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className,
  bodyClassName,
  dense,
}: {
  title?: ReactNode;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  dense?: boolean;
}) {
  return (
    <section
      className={cx(
        'flex min-w-0 flex-col rounded-lg border border-line bg-surface',
        className,
      )}
    >
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
            {title && (
              <h2 className="truncate text-[13px] font-semibold text-ink">{title}</h2>
            )}
          </div>
          {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
        </header>
      )}
      <div className={cx(dense ? 'p-0' : 'p-4', 'min-w-0 flex-1', bodyClassName)}>
        {children}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- StatusDot */

export type Tone = 'good' | 'warning' | 'serious' | 'critical' | 'accent' | 'neutral';

const TONE_TEXT: Record<Tone, string> = {
  good: 'text-good',
  warning: 'text-warning',
  serious: 'text-serious',
  critical: 'text-critical',
  accent: 'text-accent',
  neutral: 'text-ink-3',
};

const TONE_BG: Record<Tone, string> = {
  good: 'bg-good',
  warning: 'bg-warning',
  serious: 'bg-serious',
  critical: 'bg-critical',
  accent: 'bg-accent',
  neutral: 'bg-ink-3',
};

export function StatusDot({
  tone = 'neutral',
  pulse = false,
  label,
  size = 'md',
}: {
  tone?: Tone;
  pulse?: boolean;
  label?: ReactNode;
  size?: 'sm' | 'md';
}) {
  const diameter = size === 'sm' ? 'h-1.5 w-1.5' : 'h-2 w-2';
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cx('relative inline-flex', TONE_TEXT[tone])}>
        <span className={cx('rounded-full', diameter, TONE_BG[tone])} />
        {pulse && <span className={cx('pulse-ring rounded-full', diameter)} />}
      </span>
      {label && <span className="truncate">{label}</span>}
    </span>
  );
}

/* ------------------------------------------------------------------ Badge */

const BADGE_TONE: Record<Tone, string> = {
  good: 'border-good/35 bg-good/12 text-good',
  warning: 'border-warning/35 bg-warning/12 text-warning',
  serious: 'border-serious/35 bg-serious/12 text-serious',
  critical: 'border-critical/40 bg-critical/12 text-critical',
  accent: 'border-accent/35 bg-accent/12 text-accent',
  neutral: 'border-line-strong bg-surface-2 text-ink-2',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
  icon,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider whitespace-nowrap',
        BADGE_TONE[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/** Incident review state -> colour + wording, in one place. */
export function statusTone(status: string): Tone {
  switch (status) {
    case 'Open':
      return 'critical';
    case 'Confirmed':
      return 'serious';
    case 'False Positive':
      return 'neutral';
    case 'Resolved':
      return 'good';
    default:
      return 'neutral';
  }
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone(status)}>{status}</Badge>;
}

/* ----------------------------------------------------------------- Button */

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent/85 border-accent',
  secondary: 'bg-surface-2 text-ink hover:bg-surface-3 border-line-strong',
  ghost: 'bg-transparent text-ink-2 hover:text-ink hover:bg-surface-2 border-transparent',
  danger: 'bg-critical/15 text-critical hover:bg-critical/25 border-critical/40',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
}) {
  return (
    <button
      type="button"
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded border font-medium transition-colors',
        'disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-3 py-1.5 text-xs',
        BUTTON_VARIANT[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  variant = 'secondary',
  size = 'md',
  className,
  children,
  ...props
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  variant?: ButtonVariant;
  size?: 'sm' | 'md';
}) {
  return (
    <a
      href={href}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded border font-medium transition-colors',
        size === 'sm' ? 'px-2 py-1 text-[11px]' : 'px-3 py-1.5 text-xs',
        BUTTON_VARIANT[variant],
        className,
      )}
      {...props}
    >
      {children}
    </a>
  );
}

/* ------------------------------------------------------------ Empty/error */

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div
      className={cx(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-1.5 py-8' : 'gap-2 py-14',
      )}
    >
      {icon && <div className="mb-1 text-ink-3">{icon}</div>}
      <p className="text-[13px] font-medium text-ink-2">{title}</p>
      {description && (
        <p className="max-w-md text-xs leading-relaxed text-ink-3">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Unexpected error';
  return (
    <EmptyState
      icon={<AlertIcon className="h-6 w-6" />}
      title="Could not load this data"
      description={message}
      action={
        onRetry && (
          <Button onClick={onRetry} size="sm">
            Retry
          </Button>
        )
      }
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded bg-surface-2', className)} />;
}

/* --------------------------------------------------------------- Progress */

export function ProgressBar({
  value,
  tone = 'accent',
  indeterminate,
  className,
}: {
  value: number;
  tone?: Tone;
  indeterminate?: boolean;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div
      className={cx('relative h-1.5 overflow-hidden rounded-full bg-surface-3', className)}
      role="progressbar"
      aria-valuenow={indeterminate ? undefined : Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {indeterminate ? (
        <div className="indeterminate absolute inset-0" />
      ) : (
        <div
          className={cx('h-full rounded-full transition-[width] duration-500', TONE_BG[tone])}
          style={{ width: `${clamped * 100}%` }}
        />
      )}
    </div>
  );
}

/* --------------------------------------------------------- Field controls */

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx('flex flex-col gap-1', className)}>
      <span className="text-[11px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-[10px] leading-relaxed text-ink-3">{hint}</span>}
    </label>
  );
}

const CONTROL =
  'w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-xs text-ink ' +
  'placeholder:text-ink-3 focus:border-accent focus:outline-none';

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(CONTROL, props.className)} />;
}

export function Select({
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={cx(CONTROL, 'cursor-pointer', props.className)}>
      {children}
    </select>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors',
        checked ? 'border-accent bg-accent/80' : 'border-line-strong bg-surface-3',
        disabled && 'pointer-events-none opacity-45',
      )}
    >
      <span
        className={cx(
          'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-[3px]',
        )}
      />
    </button>
  );
}

/* ------------------------------------------------------------------ Modal */

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 'max-w-3xl',
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className={cx(
          'flex max-h-[90vh] w-full flex-col overflow-hidden rounded-lg border border-line-strong bg-surface shadow-2xl',
          width,
        )}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 truncate text-xs text-ink-3">{subtitle}</p>}
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            <CloseIcon className="h-4 w-4" />
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Icons */

type IconProps = { className?: string };
const strokeProps = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export function AlertIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M12 3.5 2.8 19.5h18.4L12 3.5Z" />
      <path d="M12 9.5v4.2M12 16.8v.01" />
    </svg>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

export function HelmetIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M4 15a8 8 0 0 1 16 0" />
      <path d="M2.8 15h18.4a1 1 0 0 1 1 1v1.6a1 1 0 0 1-1 1H2.8a1 1 0 0 1-1-1V16a1 1 0 0 1 1-1Z" />
      <path d="M10 7.4V15M14 7.4V15" />
    </svg>
  );
}

export function CameraIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M3 8.4 17.2 4.6l1.3 4.9L4.3 13.3 3 8.4Z" />
      <path d="M6.4 13v3.4a1.6 1.6 0 0 0 1.6 1.6h1.6" />
      <path d="M19.2 10.6 22 9.6v5l-2.2-.9" />
    </svg>
  );
}

export function SearchIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <circle cx="11" cy="11" r="6.4" />
      <path d="m20 20-3.6-3.6" />
    </svg>
  );
}

export function CheckIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="m4.5 12.5 5 5 10-11" />
    </svg>
  );
}

export function ImageIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <rect x="3" y="4.5" width="18" height="15" rx="1.8" />
      <circle cx="8.6" cy="10" r="1.6" />
      <path d="m3.6 17.4 4.9-4.6 4 3.6 3-2.6 4.9 4.2" />
    </svg>
  );
}

export function DownloadIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M12 3.6v11M7.6 10.4 12 14.8l4.4-4.4" />
      <path d="M4 17.4v1.4a1.6 1.6 0 0 0 1.6 1.6h12.8a1.6 1.6 0 0 0 1.6-1.6v-1.4" />
    </svg>
  );
}

export function RefreshIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} {...strokeProps} aria-hidden="true">
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 4v4.4h-4.4" />
    </svg>
  );
}
