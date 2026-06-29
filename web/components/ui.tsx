"use client";

import Link from "next/link";
import type { Score } from "@/lib/types";

export function ScoreBadge({ score }: { score: Score }) {
  if (!score) return null;
  const map: Record<string, string> = {
    HOT: "bg-hot text-white",
    WARM: "bg-warm text-white",
    COLD: "bg-cold text-white",
    SPAM: "bg-slate-300 text-slate-700",
  };
  const emoji: Record<string, string> = { HOT: "🔥", WARM: "🌤️", COLD: "❄️", SPAM: "🚫" };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${map[score]}`}>
      {emoji[score]} {score}
    </span>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-slate-400">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-20 text-center text-slate-400">
      <div className="text-4xl">📭</div>
      <p className="font-medium text-slate-600">{title}</p>
      {hint && <p className="text-sm">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
      <div className="text-4xl">⚠️</div>
      <p className="text-sm text-slate-600">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="tap bg-brand text-white font-medium">
          Try again
        </button>
      )}
    </div>
  );
}

export function TopBar({ title, back }: { title: string; back?: string }) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b bg-white px-4 py-3">
      {back && (
        <Link href={back} className="text-brand text-xl" aria-label="Back">
          ‹
        </Link>
      )}
      <h1 className="text-lg font-bold">{title}</h1>
    </header>
  );
}
