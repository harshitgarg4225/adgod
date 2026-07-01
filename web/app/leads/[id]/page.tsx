"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { LeadDetail } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  Button,
  Celebration,
  EmptyState,
  ErrorState,
  Icon,
  Input,
  Loading,
  ScoreBadge,
  Sheet,
  TopBar,
  useToast,
} from "@/components/ui";

export default function LeadPage() {
  const params = useParams<{ id: string }>();
  const t = useT();
  const toast = useToast();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [celebrate, setCelebrate] = useState(false);
  const [bookOpen, setBookOpen] = useState(false);
  const [slot, setSlot] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      setLead(await api.lead(params.id));
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load this lead."));
    }
  }, [params.id, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(patch: { owner_action?: string; status?: string }, msg: string) {
    setBusy(true);
    try {
      setLead(await api.patchLead(params.id, patch));
      toast.show(msg);
      if (patch.status === "WON") {
        setCelebrate(true);
        setTimeout(() => setCelebrate(false), 2600);
      }
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not update."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function book() {
    setBusy(true);
    try {
      await api.bookLead(params.id, slot ? { slot_start: new Date(slot).toISOString() } : {});
      setBookOpen(false);
      toast.show(t("leads.booked", "Appointment booked! 🗓️"));
      setLead(await api.lead(params.id));
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not book."), "error");
    } finally {
      setBusy(false);
    }
  }

  if (error && !lead) return <ErrorState message={error} onRetry={load} />;
  if (!lead) return <Loading label={t("common.loading", "Loading…")} />;

  const waLink = `https://wa.me/${lead.wa_phone.replace(/[^0-9]/g, "")}`;
  const telLink = `tel:${lead.wa_phone}`;

  return (
    <main className="min-h-[100dvh] pb-44">
      <Celebration show={celebrate} message={t("leads.wonCelebrate", "Sale won! 🎉 Shabaash!")} />
      <TopBar title={lead.name || t("leads.lead", "Lead")} back="/leads" />

      <Sheet open={bookOpen} onClose={() => setBookOpen(false)} title={t("leads.bookAppt", "Book appointment")}>
        <p className="mb-3 text-sm text-ink-muted">
          {t("leads.bookHint", "Pick a time to meet or call this lead. They'll move to your Bookings.")}
        </p>
        <Input
          label={t("leads.slot", "When")}
          type="datetime-local"
          value={slot}
          onChange={(e) => setSlot(e.target.value)}
        />
        <Button fullWidth className="mt-4" loading={busy} onClick={book}>
          {t("leads.confirmBooking", "Confirm booking")}
        </Button>
      </Sheet>

      <section className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <ScoreBadge score={lead.score} />
          <Badge>{lead.status.replace(/_/g, " ")}</Badge>
          <Badge tone="neutral">{lead.source_channel}</Badge>
        </div>

        <dl className="grid grid-cols-2 gap-2.5">
          <Field label={t("leads.wants", "Wants")} value={lead.intent_summary} />
          <Field label={t("leads.location", "Location")} value={lead.location_signal} />
          <Field label={t("leads.budget", "Budget")} value={lead.budget_signal} />
          <Field label={t("leads.timeline", "Timeline")} value={lead.timeline_signal} />
        </dl>

        <Button variant="secondary" fullWidth leftIcon="clock" onClick={() => setBookOpen(true)}>
          {lead.status === "BOOKED"
            ? t("leads.rebook", "Reschedule appointment")
            : t("leads.bookAppt", "Book appointment")}
        </Button>
      </section>

      <section className="px-4">
        <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
          {t("leads.conversation", "Conversation")}
        </h2>
        {lead.transcript.length === 0 ? (
          <EmptyState
            title={t("leads.noMessages", "No messages yet")}
            hint={t("leads.noMessagesHint", "The chat will appear here once the lead replies.")}
            icon="whatsapp"
          />
        ) : (
          <div className="flex flex-col gap-1.5">
            {lead.transcript.map((m, i) => (
              <div
                key={i}
                className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-sm shadow-xs ${
                  m.direction === "OUT"
                    ? "self-end rounded-br-md bg-brand-50 text-ink"
                    : "self-start rounded-bl-md bg-white text-ink"
                }`}
              >
                {m.body}
                <span className="mt-0.5 block text-right text-2xs text-ink-faint">
                  {new Date(m.created_at).toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Sticky action dock */}
      <div className="cta-dock space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <a
            href={waLink}
            target="_blank"
            rel="noreferrer"
            className="tap bg-brand text-white shadow-brand"
          >
            <Icon name="whatsapp" /> WhatsApp
          </a>
          <a
            href={telLink}
            className="tap border border-slate-200 bg-white text-brand"
          >
            <Icon name="phone" /> {t("leads.call", "Call")}
          </a>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => act({ owner_action: "WON", status: "WON" }, t("leads.markedWon", "Marked as Won! 🎉"))}
            className="!bg-brand-50 !text-brand-700 !border-brand-100"
          >
            {t("leads.won", "Won")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => act({ owner_action: "LOST", status: "LOST" }, t("leads.markedLost", "Marked as Lost."))}
            className="!bg-hot-light !text-hot !border-transparent"
          >
            {t("leads.lost", "Lost")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => act({ owner_action: "FOLLOWUP" }, t("leads.markedFollowup", "Saathi will follow up."))}
            className="!bg-warm-light !text-warm !border-transparent"
          >
            {t("leads.followup", "Follow-up")}
          </Button>
        </div>
      </div>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3 shadow-xs">
      <dt className="text-2xs font-medium uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-ink">{value || "—"}</dd>
    </div>
  );
}
