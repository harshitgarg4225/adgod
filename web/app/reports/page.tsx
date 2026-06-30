"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Decision, Insight } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";
import { rupees } from "@/lib/format";

export default function Reports() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [decisions, setDecisions] = useState<Decision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      const [rep, ins, dec] = await Promise.all([
        api.runReport(account),
        api.insights(account),
        api.decisions(account),
      ]);
      setMessage(rep.message);
      setInsights(ins);
      setDecisions(dec);
    } catch (e: any) {
      setError(e.userMessage || "Could not load report");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (message == null || !insights || !decisions) return <Loading label="Preparing your report…" />;

  const spend = insights.reduce((s, i) => s + i.spend_paise, 0);
  const leads = insights.reduce((s, i) => s + i.leads, 0);

  return (
    <main className="pb-10">
      <TopBar title="Reports" back="/dashboard" />
      <section className="space-y-4 p-4">
        <div className="whitespace-pre-line rounded-2xl bg-brand-light p-4 text-slate-800">
          {message}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Stat label="Total spend" value={rupees(spend)} />
          <Stat label="Leads (from ads)" value={String(leads)} />
        </div>

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">
            What Saathi did
          </h2>
          {decisions.length === 0 ? (
            <p className="text-sm text-slate-400">No changes yet — still learning.</p>
          ) : (
            <ul className="space-y-1">
              {decisions.map((d, i) => (
                <li key={i} className="flex items-center justify-between rounded-xl border p-2 text-sm">
                  <span className="font-medium">{label(d.action)}</span>
                  <span className="text-slate-400">{d.reason_code}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

function label(action: string): string {
  return (
    { PAUSE: "⏸️ Paused a weak ad set", SCALE: "📈 Scaled a winner",
      REQUEST_CREATIVE: "🎨 Refreshing tired ads", REALLOCATE: "🔀 Moved budget",
      RESUME: "▶️ Resumed an ad set" } as Record<string, string>
  )[action] || action;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-[10px] uppercase text-slate-400">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  );
}
