"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { CreativeItem } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";

export default function CreativesPage() {
  const router = useRouter();
  const [creatives, setCreatives] = useState<CreativeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      setCreatives(await api.creatives(account));
    } catch (e: any) {
      setError(e.userMessage || "Could not load creatives");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function launch() {
    setBusy(true);
    try {
      await api.launch(getUser()!.account_id!);
      router.replace("/dashboard");
    } catch (e: any) {
      setError(e.userMessage || "Could not launch");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!creatives) return <Loading label="Loading your ads…" />;

  return (
    <main className="pb-28">
      <TopBar title="Your ads are ready" back="/onboarding/brief" />
      <section className="space-y-4 p-4">
        {creatives.map((c) => (
          <article key={c.id} className="overflow-hidden rounded-2xl border">
            <div className="flex aspect-[4/5] items-center justify-center bg-brand-light text-5xl">
              🖼️
            </div>
            <div className="space-y-1 p-3">
              <p className="font-semibold">{c.headline}</p>
              <p className="text-sm text-slate-600">{c.primary_text}</p>
              <div className="flex items-center gap-2 pt-1">
                <Badge ok={c.compliance_status === "PASSED"}>
                  {c.compliance_status === "PASSED" ? "✓ Policy OK" : "✗ Needs fix"}
                </Badge>
                <span className="text-xs uppercase text-slate-400">{c.language}</span>
              </div>
            </div>
          </article>
        ))}
      </section>

      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md border-t bg-white p-3">
        <button onClick={launch} disabled={busy}
          className="tap w-full bg-brand font-semibold text-white disabled:opacity-50">
          {busy ? "Launching…" : "🚀 Launch my ads"}
        </button>
      </div>
    </main>
  );
}

function Badge({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
      {children}
    </span>
  );
}
