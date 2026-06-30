"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { SubscriptionInfo, Tier } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";

const COPY: Record<string, string> = {
  STARTER: "1 campaign · daily report",
  GROWTH: "CTWA + Lead Forms · WhatsApp bot · optimization · CRM",
  PRO: "Multi-campaign · video · wallet · CSV export · priority support",
};

export default function Billing() {
  const router = useRouter();
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getUser()?.account_id) return router.replace("/login");
    setError(null);
    try {
      const [t, s] = await Promise.all([api.tiers(), api.subscription()]);
      setTiers(t);
      setSub(s);
    } catch (e: any) {
      setError(e.userMessage || "Could not load billing");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function subscribe(tier: string) {
    setBusy(tier);
    try {
      const r = await api.subscribe(tier);
      // Open the UPI-mandate authorization page.
      window.location.href = r.mandate_url;
    } catch (e: any) {
      setError(e.userMessage || "Could not start subscription");
      setBusy(null);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!tiers || !sub) return <Loading />;

  return (
    <main className="pb-10">
      <TopBar title="Plans & billing" back="/dashboard" />
      <section className="space-y-3 p-4">
        {sub.status !== "NONE" && (
          <div className="rounded-2xl bg-brand-light p-3 text-sm">
            Current plan: <b>{sub.tier}</b> · {sub.status}
            {sub.trial_end && <> · trial ends {new Date(sub.trial_end).toLocaleDateString()}</>}
          </div>
        )}
        {tiers.map((t) => {
          const active = sub.tier === t.tier;
          return (
            <article key={t.tier} className={`rounded-2xl border p-4 ${active ? "border-brand" : ""}`}>
              <div className="flex items-baseline justify-between">
                <h2 className="text-lg font-bold">{t.tier}</h2>
                <span className="font-semibold">{t.price_display}/mo</span>
              </div>
              <p className="mt-1 text-sm text-slate-500">{COPY[t.tier]}</p>
              <p className="mt-1 text-xs text-slate-400">incl. 18% GST · 7-day free trial</p>
              <button
                onClick={() => subscribe(t.tier)}
                disabled={!!busy || active}
                className={`tap mt-3 w-full font-semibold ${active ? "bg-slate-100 text-slate-400" : "bg-brand text-white"}`}
              >
                {active ? "Current plan" : busy === t.tier ? "Starting…" : "Choose plan (UPI)"}
              </button>
            </article>
          );
        })}
      </section>
    </main>
  );
}
