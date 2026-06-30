"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Angle, Brief } from "@/lib/types";
import { ErrorState, Loading, TopBar } from "@/components/ui";

export default function BriefPage() {
  const router = useRouter();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [angles, setAngles] = useState<Angle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      const [b, a] = await Promise.all([api.brief(account), api.angles(account)]);
      setBrief(b);
      setAngles(a);
    } catch (e: any) {
      setError(e.userMessage || "Could not load");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function createAds() {
    setBusy(true);
    try {
      await api.generateCreatives(getUser()!.account_id!);
      router.replace("/onboarding/creatives");
    } catch (e: any) {
      setError(e.userMessage || "Could not generate ads");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!brief || !angles) return <Loading label="Saathi is understanding your business…" />;

  return (
    <main className="pb-28">
      <TopBar title="Here's what we understood" back="/onboarding" />
      <section className="space-y-4 p-4">
        <Card title="Your offer">{brief.offer || "—"}</Card>
        <Card title="Who we'll target">{(brief.audience || []).join(", ") || "—"}</Card>
        <Card title="Why people choose you">{(brief.usp || []).join(", ") || "—"}</Card>

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">
            Ad angles Saathi will test ({angles.length})
          </h2>
          <ul className="space-y-2">
            {angles.map((a) => (
              <li key={a.id} className="rounded-2xl border p-3">
                <p className="font-semibold">{a.title}</p>
                <p className="text-sm text-slate-500">{a.hypothesis}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md border-t bg-white p-3">
        <button onClick={createAds} disabled={busy}
          className="tap w-full bg-brand font-semibold text-white disabled:opacity-50">
          {busy ? "Writing your ads…" : "Looks good → Create my ads"}
        </button>
      </div>
    </main>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border p-3">
      <p className="text-[10px] uppercase text-slate-400">{title}</p>
      <p className="text-slate-800">{children}</p>
    </div>
  );
}
