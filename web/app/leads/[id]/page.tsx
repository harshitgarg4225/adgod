"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { LeadDetail } from "@/lib/types";
import { ErrorState, Loading, ScoreBadge, TopBar } from "@/components/ui";

export default function LeadPage() {
  const params = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setLead(await api.lead(params.id));
    } catch (e: any) {
      setError(e.userMessage || "Could not load this lead");
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(patch: { owner_action?: string; status?: string }) {
    setBusy(true);
    try {
      setLead(await api.patchLead(params.id, patch));
    } catch (e: any) {
      setError(e.userMessage || "Could not update");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!lead) return <Loading />;

  const waLink = `https://wa.me/${lead.wa_phone.replace(/[^0-9]/g, "")}`;
  const telLink = `tel:${lead.wa_phone}`;

  return (
    <main className="pb-28">
      <TopBar title={lead.name || "Lead"} back="/dashboard" />

      <section className="space-y-3 p-4">
        <div className="flex items-center gap-2">
          <ScoreBadge score={lead.score} />
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
            {lead.status}
          </span>
          <span className="text-xs text-slate-400">{lead.source_channel}</span>
        </div>

        <dl className="grid grid-cols-2 gap-2 text-sm">
          <Field label="Wants" value={lead.intent_summary} />
          <Field label="Location" value={lead.location_signal} />
          <Field label="Budget" value={lead.budget_signal} />
          <Field label="Timeline" value={lead.timeline_signal} />
        </dl>
      </section>

      <section className="px-4">
        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-slate-400">
          Conversation
        </h2>
        <div className="flex flex-col gap-2">
          {lead.transcript.map((m, i) => (
            <div
              key={i}
              className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                m.direction === "OUT"
                  ? "self-end bg-brand-light text-slate-800"
                  : "self-start bg-slate-100 text-slate-800"
              }`}
            >
              {m.body}
            </div>
          ))}
        </div>
      </section>

      {/* Sticky action bar (PRD §6.7.1 one-tap Call/WhatsApp/Won/Lost). */}
      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md border-t bg-white p-3">
        <div className="grid grid-cols-2 gap-2">
          <a href={waLink} target="_blank" className="tap flex items-center justify-center bg-brand font-semibold text-white">
            💬 WhatsApp
          </a>
          <a href={telLink} className="tap flex items-center justify-center border font-semibold text-brand">
            📞 Call
          </a>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <button disabled={busy} onClick={() => act({ owner_action: "WON", status: "WON" })} className="tap bg-emerald-50 text-emerald-700 text-sm font-medium">
            Won
          </button>
          <button disabled={busy} onClick={() => act({ owner_action: "LOST", status: "LOST" })} className="tap bg-rose-50 text-rose-700 text-sm font-medium">
            Lost
          </button>
          <button disabled={busy} onClick={() => act({ owner_action: "FOLLOWUP" })} className="tap bg-amber-50 text-amber-700 text-sm font-medium">
            Follow-up
          </button>
        </div>
      </div>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-xl border p-2">
      <dt className="text-[10px] uppercase text-slate-400">{label}</dt>
      <dd className="text-slate-800">{value || "—"}</dd>
    </div>
  );
}
