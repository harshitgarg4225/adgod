"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, enterClient } from "@/lib/api";
import type { AdminAccount, AnomalyEvent, FeatureFlag } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";

export default function Admin() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [accounts, setAccounts] = useState<AdminAccount[] | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyEvent[] | null>(null);
  const [flags, setFlags] = useState<FeatureFlag[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [a, an, f] = await Promise.all([
        api.adminAccounts(q),
        api.adminAnomalies(),
        api.adminFlags(),
      ]);
      setAccounts(a);
      setAnomalies(an);
      setFlags(f);
    } catch (e: any) {
      if (e.status === 403) return router.replace("/dashboard");
      setError(e.userMessage || "Could not load");
    }
  }, [q, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function pause(id: string) {
    await api.adminPause(id);
    setMsg("Account paused");
    load();
  }
  async function toggle(f: FeatureFlag) {
    await api.adminSetFlag(f.key, !f.enabled);
    load();
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!accounts || !anomalies || !flags) return <Loading />;

  return (
    <main className="pb-10">
      <TopBar title="Admin / Ops" back="/dashboard" />
      <section className="space-y-5 p-4">
        {msg && <p className="rounded-xl bg-emerald-50 p-2 text-sm text-emerald-700">{msg}</p>}

        <div>
          <div className="flex gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search accounts…"
              className="tap flex-1 border" />
          </div>
          <ul className="mt-2 space-y-2">
            {accounts.map((a) => (
              <li key={a.id} className="rounded-2xl border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">{a.business_name}</p>
                    <p className="text-xs text-slate-500">
                      {a.phase} · {a.autopilot} · trust {a.trust_score}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-600">
                      Today: {(a as any).today_spend_display ?? "₹0"} · leads {(a as any).leads_today ?? 0}
                      {" · "}
                      <span className={(a as any).meta_status === "ERROR" ? "font-semibold text-rose-600" : ""}>
                        Meta {(a as any).meta_status ?? "NONE"}
                      </span>
                    </p>
                  </div>
                </div>
                <div className="mt-2 flex gap-2">
                  <button onClick={() => pause(a.id)} className="rounded-lg bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700">
                    Pause
                  </button>
                  <button
                    onClick={() =>
                      api.adminImpersonate(a.id).then((r) => {
                        // Swap into the client's session (audited server-side) — same
                        // machinery the partner console uses.
                        enterClient(r.access, a.id, a.business_name);
                        router.push("/dashboard");
                      })
                    }
                    className="rounded-lg border px-3 py-1.5 text-xs font-medium">
                    Open as client
                  </button>
                  <button
                    onClick={() => api.adminMarkPaid(a.id).then(() => setMsg("Marked paid (ACTIVE)")).catch((e: any) => setMsg(e.userMessage || "No subscription"))}
                    className="rounded-lg border px-3 py-1.5 text-xs font-medium">
                    Mark paid
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">Anomaly queue</h2>
          {anomalies.length === 0 ? (
            <p className="text-sm text-slate-400">No anomalies. 🎉</p>
          ) : (
            <ul className="space-y-1">
              {anomalies.map((e) => (
                <li key={e.id} className="rounded-xl border p-2 text-sm">
                  <span className="font-medium text-rose-600">{e.severity}</span> ·{" "}
                  <span className="font-medium">{(e as any).business_name ?? "?"}</span> ·{" "}
                  {String((e.detail as any).reason ?? "anomaly")} · {e.action_taken}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">Daily digest</h2>
          <DigestPanel />
        </div>

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">Feature flags</h2>
          {flags.length === 0 ? (
            <p className="text-sm text-slate-400">No flags yet.</p>
          ) : (
            <ul className="space-y-1">
              {flags.map((f) => (
                <li key={f.key} className="flex items-center justify-between rounded-xl border p-2 text-sm">
                  <span>{f.key}</span>
                  <button onClick={() => toggle(f)}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${f.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                    {f.enabled ? "ON" : "OFF"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

function DigestPanel() {
  const [digest, setDigest] = useState<{ date: string; clients: any[] } | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    api.adminDigest().then(setDigest).catch(() => setDigest({ date: "", clients: [] }));
  }, []);

  if (!digest) return <p className="text-sm text-slate-400">Loading…</p>;
  if (digest.clients.length === 0)
    return <p className="text-sm text-slate-400">No live clients yet.</p>;
  return (
    <ul className="space-y-2">
      {digest.clients.map((c) => (
        <li key={c.account_id} className="rounded-xl border p-3 text-sm">
          <div className="flex items-center justify-between">
            <p className="font-semibold">{c.business_name}</p>
            <button
              className="rounded-lg border px-2 py-1 text-xs"
              onClick={() => {
                navigator.clipboard.writeText(c.text.replace(/\\n/g, "\n"));
                setCopied(c.account_id);
                setTimeout(() => setCopied(null), 1500);
              }}
            >
              {copied === c.account_id ? "Copied ✓" : "Copy for WhatsApp"}
            </button>
          </div>
          <p className="mt-1 text-slate-600">
            Spend ₹{Math.round(c.spend_paise / 100)} · Enquiries {c.enquiries} · Qualified {c.qualified}
          </p>
        </li>
      ))}
    </ul>
  );
}
