"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, clearSession, getUser } from "@/lib/api";
import type { Home, LeadListItem } from "@/lib/types";
import { EmptyState, ErrorState, Loading, ScoreBadge } from "@/components/ui";

export default function Dashboard() {
  const router = useRouter();
  const [home, setHome] = useState<Home | null>(null);
  const [leads, setLeads] = useState<LeadListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const user = getUser();
    if (!user?.account_id) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      const [h, l] = await Promise.all([
        api.home(user.account_id),
        api.leads(user.account_id),
      ]);
      setHome(h);
      setLeads(l);
    } catch (e: any) {
      if (e.status === 401) {
        clearSession();
        router.replace("/login");
        return;
      }
      setError(e.userMessage || "Could not load your dashboard");
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!home || !leads) return <Loading label="Loading your leads…" />;

  return (
    <main className="pb-10">
      <header className="bg-brand px-5 pb-6 pt-5 text-white">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs opacity-80">Namaste 👋</p>
            <h1 className="text-xl font-bold">{getUser()?.name || "Owner"}</h1>
          </div>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className="text-xs underline opacity-80"
          >
            Logout
          </button>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <Stat label="Spent today" value={home.today_spend_display} />
          <Stat label="Enquiries" value={String(home.enquiries_today)} />
          <Stat label="Qualified" value={String(home.qualified_today)} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {home.campaign_status.map((s) => (
            <span key={s} className="rounded-full bg-white/20 px-3 py-1 text-xs">
              {s}
            </span>
          ))}
          {home.cpql_display && (
            <span className="rounded-full bg-white/20 px-3 py-1 text-xs">
              CPQL {home.cpql_display}
            </span>
          )}
        </div>
      </header>

      <nav className="grid grid-cols-3 gap-2 px-4 pt-4">
        <Quick href="/onboarding" icon="✨" label="Set up ads" />
        <Quick href="/reports" icon="📊" label="Reports" />
        <Quick href="/billing" icon="💳" label="Billing" />
        {(getUser()?.role === "PARTNER" || getUser()?.role === "ADMIN") && (
          <Quick href="/partner" icon="🧑‍💼" label="Clients" />
        )}
        {(getUser()?.role === "ADMIN" || getUser()?.role === "OPS") && (
          <Quick href="/admin" icon="🛠️" label="Admin" />
        )}
      </nav>

      <section className="px-4 pt-4">
        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">
          Leads
        </h2>
        {leads.length === 0 ? (
          <EmptyState title="No leads yet" hint="Your ads are live — leads will appear here." />
        ) : (
          <ul className="flex flex-col gap-2">
            {leads.map((lead) => (
              <li key={lead.id}>
                <Link
                  href={`/leads/${lead.id}`}
                  className="flex items-center justify-between rounded-2xl border bg-white p-3 active:bg-slate-50"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-semibold">
                        {lead.name || "New enquiry"}
                      </span>
                      <ScoreBadge score={lead.score} />
                    </div>
                    <p className="truncate text-sm text-slate-500">
                      {lead.intent_summary || lead.status}
                    </p>
                  </div>
                  <span className="text-slate-300">›</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/15 p-3">
      <p className="text-[10px] uppercase opacity-80">{label}</p>
      <p className="text-lg font-bold">{value}</p>
    </div>
  );
}

function Quick({ href, icon, label }: { href: string; icon: string; label: string }) {
  return (
    <Link href={href} className="flex flex-col items-center gap-1 rounded-2xl border p-3 active:bg-slate-50">
      <span className="text-xl">{icon}</span>
      <span className="text-xs font-medium text-slate-600">{label}</span>
    </Link>
  );
}
