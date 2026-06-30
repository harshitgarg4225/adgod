"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { PartnerSubAccount, Rollup } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";
import { rupees } from "@/lib/format";

export default function Partner() {
  const router = useRouter();
  const [subs, setSubs] = useState<PartnerSubAccount[] | null>(null);
  const [roll, setRoll] = useState<Rollup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, r] = await Promise.all([api.partnerSubAccounts(), api.partnerRollup()]);
      setSubs(s);
      setRoll(r);
    } catch (e: any) {
      if (e.status === 403) return router.replace("/dashboard");
      setError(e.userMessage || "Could not load");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.partnerCreate({ business_name: name, category: "coaching", city: "" });
      setName("");
      await load();
    } catch (e: any) {
      setError(e.userMessage || "Could not create");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!subs || !roll) return <Loading />;

  return (
    <main className="pb-10">
      <TopBar title="Partner console" back="/dashboard" />
      <section className="space-y-4 p-4">
        <div className="grid grid-cols-2 gap-2">
          <Stat label="Clients" value={`${roll.accounts} (${roll.live} live)`} />
          <Stat label="Avg CPQL" value={rupees(roll.avg_cpql_paise)} />
          <Stat label="Total spend" value={rupees(roll.total_spend_paise)} />
          <Stat label="Qualified leads" value={String(roll.qualified_leads)} />
        </div>

        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="New client name" className="tap flex-1 border" />
          <button onClick={create} disabled={busy} className="tap bg-brand px-4 font-semibold text-white">
            Add
          </button>
        </div>

        <ul className="space-y-2">
          {subs.map((s) => (
            <li key={s.account_id} className="flex items-center justify-between rounded-2xl border p-3">
              <div>
                <p className="font-semibold">{s.business_name}</p>
                <p className="text-xs text-slate-500">{s.category} · {s.phase}</p>
              </div>
              <div className="text-right text-sm">
                <p className="font-medium">{rupees(s.cpql_paise)} <span className="text-xs text-slate-400">CPQL</span></p>
                <p className="text-xs text-slate-500">{s.qualified_24h} qualified / 24h</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-[10px] uppercase text-slate-400">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  );
}
