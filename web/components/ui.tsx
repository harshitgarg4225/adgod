"use client";

/**
 * Salmor UI kit — the single source of truth for interactive primitives.
 *
 * Every control has explicit hover / active / focus-visible / disabled / loading states,
 * uses the design tokens (no ad-hoc colours), and is built mobile-first with 48px tap
 * targets. Emoji are replaced by a consistent inline-SVG icon set so glyphs render the
 * same on every Android OEM. Saathi has a real avatar so the "companion" promise is felt.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useT } from "@/lib/i18n";
import type { Score } from "@/lib/types";

/* ───────────────────────────── Icons ───────────────────────────── */

const ICONS: Record<string, string> = {
  home: "M3 11.5 12 4l9 7.5M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9",
  leads: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 20a8 8 0 0 1 16 0",
  reports: "M4 19V5m0 14h16M8 16v-5m4 5V8m4 8v-3",
  billing: "M3 7h18v10H3zM3 11h18",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a7.4 7.4 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7.3 7.3 0 0 0-2-1.2L14.5 2h-5l-.4 2.6a7.3 7.3 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7.4 7.4 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7.3 7.3 0 0 0 2 1.2l.4 2.6h5l.4-2.6a7.3 7.3 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.06-.4.1-.8.1-1.2Z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
  check: "M20 6 9 17l-5-5",
  x: "M18 6 6 18M6 6l12 12",
  chevronRight: "M9 6l6 6-6 6",
  chevronLeft: "M15 6l-6 6 6 6",
  phone:
    "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L20 13l1 4v2a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z",
  whatsapp:
    "M12 3a9 9 0 0 0-7.7 13.6L3 21l4.5-1.2A9 9 0 1 0 12 3Zm-3 5c.2 0 .5 0 .7.5l.7 1.6c.1.3 0 .5-.1.7l-.5.6c-.2.2-.2.4-.1.6a6 6 0 0 0 2.8 2.5c.3.1.5.1.7-.1l.5-.7c.2-.2.4-.2.6-.1l1.6.8c.3.1.4.3.4.6 0 1-.8 1.8-1.8 1.8A7 7 0 0 1 7 10C7 9 7.8 8 9 8Z",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3ZM5 11a7 7 0 0 0 14 0M12 18v3",
  sparkle:
    "M12 3l1.8 4.7L18.5 9l-4.7 1.3L12 15l-1.8-4.7L5.5 9l4.7-1.3L12 3ZM19 14l.9 2.3 2.3.9-2.3.9L19 20l-.9-2.3-2.3-.9 2.3-.9L19 14Z",
  pause: "M9 5v14M15 5v14",
  play: "M7 5l12 7-12 7V5Z",
  plus: "M12 5v14M5 12h14",
  download: "M12 3v12m0 0l-4-4m4 4l4-4M5 21h14",
  alert: "M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3Z",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z",
};

export function Icon({
  name,
  className = "h-5 w-5",
  strokeWidth = 1.8,
  filled = false,
}: {
  name: keyof typeof ICONS | string;
  className?: string;
  strokeWidth?: number;
  filled?: boolean;
}) {
  const d = ICONS[name] ?? "";
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}

/* ───────────────────────────── Brand ───────────────────────────── */

/** Saathi — a friendly companion mark used in headers, loading and empty states. */
export function SaathiAvatar({ size = 40, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      className={className}
      role="img"
      aria-label="Saathi"
    >
      <defs>
        <linearGradient id="saathi-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#36B981" />
          <stop offset="1" stopColor="#0B7A4B" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="14" fill="url(#saathi-g)" />
      <circle cx="18" cy="22" r="3.4" fill="#fff" />
      <circle cx="30" cy="22" r="3.4" fill="#fff" />
      <circle cx="18.8" cy="22.6" r="1.5" fill="#075c39" />
      <circle cx="30.8" cy="22.6" r="1.5" fill="#075c39" />
      <path d="M17 30c2 2.4 5 3.4 7 3.4s5-1 7-3.4" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <path d="M24 7l1.6 3.4L29 12l-3.4 1.6L24 17l-1.6-3.4L19 12l3.4-1.6L24 7Z" fill="#FEF1E2" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-bold tracking-tight ${className}`}>
      <SaathiAvatar size={28} />
      <span>Salmor</span>
    </span>
  );
}

/* ───────────────────────────── Button ───────────────────────────── */

type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "accent";
  size?: "md" | "lg" | "sm";
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

const VARIANT: Record<string, string> = {
  primary: "bg-brand text-white shadow-brand hover:bg-brand-600 active:bg-brand-700",
  accent: "bg-accent text-white shadow-card hover:bg-accent-500 active:bg-accent-600",
  secondary: "bg-white text-ink border border-slate-200 hover:bg-slate-50 active:bg-slate-100",
  ghost: "bg-transparent text-brand hover:bg-brand-50 active:bg-brand-100",
  danger: "bg-hot text-white hover:brightness-95 active:brightness-90",
};
const SIZE: Record<string, string> = {
  sm: "min-h-[40px] px-4 text-sm rounded-lg",
  md: "min-h-[48px] px-5 text-base rounded-xl",
  lg: "min-h-[54px] px-6 text-lg rounded-2xl",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  leftIcon,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-semibold transition
        active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50
        ${VARIANT[variant]} ${SIZE[size]} ${fullWidth ? "w-full" : ""} ${className}`}
    >
      {loading ? (
        <Spinner className="h-5 w-5" />
      ) : leftIcon ? (
        <Icon name={leftIcon} className="h-5 w-5" />
      ) : null}
      {children}
    </button>
  );
}

export function Spinner({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

/* ───────────────────────────── Inputs ───────────────────────────── */

type FieldProps = {
  label?: string;
  hint?: string;
  error?: string;
  voice?: boolean;
} & React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ label, hint, error, voice, className = "", id, ...rest }: FieldProps) {
  const fieldId = id || rest.name || label;
  const onVoice = useVoiceInput((text) => {
    const el = document.getElementById(String(fieldId)) as HTMLInputElement | null;
    if (el) {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      )?.set;
      setter?.call(el, text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={String(fieldId)} className="text-sm font-medium text-ink-soft">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={String(fieldId)}
          {...rest}
          className={`w-full rounded-xl border bg-white px-4 py-3 text-base text-ink
            placeholder:text-ink-faint transition focus:border-brand
            ${error ? "border-hot" : "border-slate-200"} ${voice ? "pr-12" : ""} ${className}`}
        />
        {voice && (
          <button
            type="button"
            onClick={onVoice}
            aria-label="Speak to fill"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-brand
              hover:bg-brand-50 active:scale-95"
          >
            <Icon name="mic" />
          </button>
        )}
      </div>
      {error ? (
        <p className="text-sm text-hot">{error}</p>
      ) : hint ? (
        <p className="text-sm text-ink-faint">{hint}</p>
      ) : null}
    </div>
  );
}

export function Textarea({
  label,
  hint,
  error,
  voice,
  className = "",
  id,
  ...rest
}: { label?: string; hint?: string; error?: string; voice?: boolean } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const fieldId = id || rest.name || label;
  const onVoice = useVoiceInput((text) => {
    const el = document.getElementById(String(fieldId)) as HTMLTextAreaElement | null;
    if (el) {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      )?.set;
      setter?.call(el, (el.value ? el.value + " " : "") + text);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={String(fieldId)} className="text-sm font-medium text-ink-soft">
          {label}
        </label>
      )}
      <div className="relative">
        <textarea
          id={String(fieldId)}
          {...rest}
          className={`w-full rounded-xl border bg-white px-4 py-3 text-base text-ink
            placeholder:text-ink-faint transition focus:border-brand
            ${error ? "border-hot" : "border-slate-200"} ${className}`}
        />
        {voice && (
          <button
            type="button"
            onClick={onVoice}
            aria-label="Speak to fill"
            className="absolute right-2 top-2 rounded-lg p-2 text-brand hover:bg-brand-50 active:scale-95"
          >
            <Icon name="mic" />
          </button>
        )}
      </div>
      {error ? (
        <p className="text-sm text-hot">{error}</p>
      ) : hint ? (
        <p className="text-sm text-ink-faint">{hint}</p>
      ) : null}
    </div>
  );
}

/** Web Speech API voice-to-text — graceful no-op where unsupported. */
function useVoiceInput(onResult: (text: string) => void) {
  return useCallback(() => {
    const SR =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      alert("Voice input isn't supported on this browser.");
      return;
    }
    const rec = new SR();
    rec.lang =
      (typeof document !== "undefined" && document.documentElement.lang === "hi"
        ? "hi-IN"
        : "en-IN");
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e: any) => onResult(e.results[0][0].transcript);
    rec.start();
  }, [onResult]);
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-7 w-12 items-center rounded-full transition
        ${checked ? "bg-brand" : "bg-slate-300"}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition
          ${checked ? "translate-x-6" : "translate-x-1"}`}
      />
    </button>
  );
}

/* ───────────────────────────── Surfaces ───────────────────────────── */

export function Card({
  className = "",
  children,
  as = "div",
}: {
  className?: string;
  children: React.ReactNode;
  as?: "div" | "section";
}) {
  const C = as;
  return (
    <C className={`rounded-2xl border border-slate-100 bg-white p-4 shadow-card ${className}`}>
      {children}
    </C>
  );
}

export function Stat({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: { value: string; up: boolean };
  tone?: "neutral" | "brand" | "accent";
}) {
  const toneCls =
    tone === "brand" ? "text-brand" : tone === "accent" ? "text-accent" : "text-ink";
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${toneCls}`}>{value}</p>
      {delta && (
        <p className={`mt-0.5 text-xs font-medium ${delta.up ? "text-brand" : "text-hot"}`}>
          {delta.up ? "▲" : "▼"} {delta.value}
        </p>
      )}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "brand" | "accent" | "hot" | "warm" | "cold" | "success";
}) {
  const map: Record<string, string> = {
    neutral: "bg-slate-100 text-ink-soft",
    brand: "bg-brand-50 text-brand-700",
    accent: "bg-accent-light text-accent-600",
    success: "bg-brand-50 text-brand-700",
    hot: "bg-hot-light text-hot",
    warm: "bg-warm-light text-warm",
    cold: "bg-cold-light text-cold",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${map[tone]}`}
    >
      {children}
    </span>
  );
}

export function ScoreBadge({ score }: { score: Score }) {
  const t = useT();
  if (!score) return null;
  const tone: Record<string, "hot" | "warm" | "cold" | "neutral"> = {
    HOT: "hot",
    WARM: "warm",
    COLD: "cold",
    SPAM: "neutral",
  };
  const label: Record<string, string> = {
    HOT: t("leads.hot", "Hot lead"),
    WARM: t("leads.warm", "Warm"),
    COLD: t("leads.cold", "Cold"),
    SPAM: t("leads.spam", "Spam"),
  };
  const dot: Record<string, string> = {
    HOT: "bg-hot",
    WARM: "bg-warm",
    COLD: "bg-cold",
    SPAM: "bg-slate-400",
  };
  return (
    <Badge tone={tone[score]}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot[score]}`} aria-hidden />
      {label[score]}
    </Badge>
  );
}

/* ───────────────────────────── States ───────────────────────────── */

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-20 text-ink-faint"
      role="status"
      aria-live="polite"
    >
      <SaathiAvatar size={44} className="animate-pulse" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-card">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-6 w-32" />
      <Skeleton className="mt-3 h-3 w-full" />
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  icon = "sparkle",
  action,
}: {
  title: string;
  hint?: string;
  icon?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-8 py-16 text-center animate-fade-in">
      <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-brand-50 text-brand">
        <Icon name={icon} className="h-9 w-9" />
      </div>
      <p className="text-lg font-semibold text-ink">{title}</p>
      {hint && <p className="max-w-xs text-sm text-ink-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const t = useT();
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 px-8 py-16 text-center"
      role="alert"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-hot-light text-hot">
        <Icon name="alert" className="h-8 w-8" />
      </div>
      <p className="text-sm text-ink-soft">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" leftIcon="clock" onClick={onRetry}>
          {t("common.tryAgain", "Try again")}
        </Button>
      )}
    </div>
  );
}

/* ───────────────────────────── Navigation ───────────────────────────── */

export function TopBar({
  title,
  back,
  right,
}: {
  title: string;
  back?: string | true;
  right?: React.ReactNode;
}) {
  const router = useRouter();
  return (
    <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-slate-100 bg-white/90 px-3 py-3 backdrop-blur">
      {back &&
        (back === true ? (
          <button
            onClick={() => router.back()}
            aria-label="Back"
            className="flex h-10 w-10 items-center justify-center rounded-full text-ink-soft hover:bg-slate-100"
          >
            <Icon name="chevronLeft" />
          </button>
        ) : (
          <Link
            href={back}
            aria-label="Back"
            className="flex h-10 w-10 items-center justify-center rounded-full text-ink-soft hover:bg-slate-100"
          >
            <Icon name="chevronLeft" />
          </Link>
        ))}
      <h1 className="flex-1 truncate text-lg font-bold">{title}</h1>
      {right}
    </header>
  );
}

const NAV = [
  { href: "/dashboard", icon: "home", key: "nav.home", en: "Home" },
  { href: "/leads", icon: "leads", key: "nav.leads", en: "Leads" },
  { href: "/reports", icon: "reports", key: "nav.reports", en: "Reports" },
  { href: "/billing", icon: "billing", key: "nav.billing", en: "Billing" },
];

export function BottomNav({ active }: { active: string }) {
  const t = useT();
  return (
    <nav className="cta-dock flex items-stretch justify-around !pt-2" aria-label="Primary">
      {NAV.map((n) => {
        const on = active === n.href;
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={on ? "page" : undefined}
            className={`flex flex-1 flex-col items-center gap-1 rounded-lg py-1.5 text-2xs font-medium
              ${on ? "text-brand" : "text-ink-faint"}`}
          >
            <Icon name={n.icon} className="h-6 w-6" filled={on} strokeWidth={on ? 0.6 : 1.8} />
            {t(n.key, n.en)}
          </Link>
        );
      })}
    </nav>
  );
}

/* ───────────────────────────── Toast ───────────────────────────── */

type Toast = { id: number; message: string; tone: "success" | "error" | "info" };
const ToastCtx = createContext<{ show: (m: string, t?: Toast["tone"]) => void } | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);
  const show = useCallback((message: string, tone: Toast["tone"] = "success") => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-50 mx-auto flex max-w-[28rem] flex-col gap-2 px-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium text-white shadow-float animate-slide-up
              ${t.tone === "error" ? "bg-hot" : t.tone === "info" ? "bg-ink" : "bg-brand"}`}
          >
            <Icon name={t.tone === "error" ? "alert" : "check"} className="h-5 w-5" />
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  return ctx ?? { show: () => {} };
}

/* ───────────────────────────── Bottom sheet / confirm ───────────────────────────── */

export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-ink/40 animate-fade-in" onClick={onClose} />
      <div className="relative mx-auto w-full max-w-[30rem] rounded-t-3xl bg-white p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] shadow-float animate-sheet-up">
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-slate-200" />
        {title && <h2 className="mb-3 text-lg font-bold">{title}</h2>}
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  tone = "primary",
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  body?: string;
  confirmLabel?: string;
  tone?: "primary" | "danger";
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useT();
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      {body && <p className="mb-5 text-sm text-ink-muted">{body}</p>}
      <div className="flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>
          {t("common.cancel", "Cancel")}
        </Button>
        <Button
          variant={tone === "danger" ? "danger" : "primary"}
          fullWidth
          onClick={() => {
            onConfirm();
            onClose();
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </Sheet>
  );
}

/* ───────────────────────────── Celebration ───────────────────────────── */

export function Celebration({ show, message }: { show: boolean; message: string }) {
  if (!show) return null;
  const bits = Array.from({ length: 18 });
  const colors = ["#0B7A4B", "#36B981", "#F2820D", "#F8B25B", "#E11D48"];
  return (
    <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden">
      {bits.map((_, i) => (
        <span
          key={i}
          className="absolute top-0 h-2.5 w-2.5 rounded-sm animate-slide-up"
          style={{
            left: `${(i * 53) % 100}%`,
            background: colors[i % colors.length],
            transform: `translateY(${20 + (i % 5) * 12}vh) rotate(${i * 40}deg)`,
            animationDelay: `${(i % 6) * 70}ms`,
          }}
        />
      ))}
      <div className="absolute inset-x-0 top-1/3 flex justify-center px-8">
        <div className="rounded-3xl bg-white px-6 py-4 text-center shadow-float animate-pop">
          <div className="mb-1 flex justify-center">
            <SaathiAvatar size={48} />
          </div>
          <p className="text-lg font-bold text-ink">{message}</p>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────────── Charts (dependency-free SVG) ───────────────────────────── */

export function BarChart({
  data,
  height = 120,
  color = "#0B7A4B",
}: {
  data: { label: string; value: number }[];
  height?: number;
  color?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="flex items-end gap-2" style={{ height }}>
      {data.map((d, i) => (
        <div key={i} className="flex flex-1 flex-col items-center justify-end gap-1">
          <div
            className="w-full rounded-t-lg transition-all"
            style={{ height: `${(d.value / max) * (height - 24)}px`, background: color, minHeight: 3 }}
            title={`${d.label}: ${d.value}`}
          />
          <span className="text-2xs text-ink-faint">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({
  points,
  color = "#0B7A4B",
  width = 120,
  height = 36,
}: {
  points: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  if (points.length < 2) return null;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${i * step} ${height - ((p - min) / span) * height}`)
    .join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden>
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ───────────────────────────── Offline banner ───────────────────────────── */

export function OfflineBanner() {
  const t = useT();
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="sticky top-0 z-40 flex items-center justify-center gap-2 bg-ink px-4 py-2 text-xs font-medium text-white">
      <Icon name="alert" className="h-4 w-4" />
      {t("common.offline", "You're offline — we'll retry when you reconnect.")}
    </div>
  );
}

/* ───────────────────────────── Saathi status ───────────────────────────── */

export function ActingAsBanner({ name, onExit }: { name: string; onExit: () => void }) {
  return (
    <div className="sticky top-0 z-40 flex items-center justify-between gap-2 bg-accent px-4 py-2 text-sm font-medium text-white">
      <span className="truncate">
        {"Viewing "}
        <b>{name}</b>
      </span>
      <button onClick={onExit} className="shrink-0 rounded-lg bg-white/20 px-3 py-1 text-xs font-semibold">
        Back to agency
      </button>
    </div>
  );
}

export function SaathiStatusCard({ line }: { line: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-gradient-to-br from-brand to-brand-700 p-4 text-white shadow-brand">
      <SaathiAvatar size={40} />
      <div className="min-w-0">
        <p className="text-2xs font-semibold uppercase tracking-wide text-white/70">Saathi</p>
        <p className="truncate text-sm font-medium">{line}</p>
      </div>
    </div>
  );
}
