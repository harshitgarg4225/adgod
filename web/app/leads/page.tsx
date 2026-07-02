"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { LeadListItem } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  BottomNav,
  Button,
  EmptyState,
  ErrorState,
  Icon,
  OfflineBanner,
  ScoreBadge,
  SkeletonCard,
  TopBar,
  useToast,
} from "@/components/ui";

type Filter = { key: string; en: string; score?: string; status?: string };

export default function LeadsInbox() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [leads, setLeads] = useState<LeadListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  // Manual entry — on the own-number path enquiries land in the owner's WhatsApp, so
  // logging them here is what makes the inbox and reports real.
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPhone, setNewPhone] = useState("");
  const [newNote, setNewNote] = useState("");
  const [saving, setSaving] = useState(false);

  async function addLead() {
    const account = getUser()?.account_id;
    if (!account || !newPhone.trim()) return;
    setSaving(true);
    try {
      await api.createLead(account, {
        name: newName.trim() || undefined,
        wa_phone: newPhone.trim(),
        intent_summary: newNote.trim() || undefined,
      });
      setAdding(false);
      setNewName(""); setNewPhone(""); setNewNote("");
      toast.show(t("leads.added", "Lead added"), "success");
      load();
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not add."), "error");
    } finally {
      setSaving(false);
    }
  }

  const filters: Filter[] = [
    { key: "all", en: "All" },
    { key: "hot", en: "Hot", score: "HOT" },
    { key: "warm", en: "Warm", score: "WARM" },
    { key: "won", en: "Won", status: "WON" },
  ];

  const load = useCallback(async () => {
    const user = getUser();
    if (!user?.account_id) {
      router.replace("/login");
      return;
    }
    setError(null);
    setLeads(null);
    try {
      const f = filters[active];
      const l = await api.leads(user.account_id, {
        q: q || undefined,
        score: f.score,
        status: f.status,
      });
      setLeads(l);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load leads."));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router, active, q, t]);

  useEffect(() => {
    const id = setTimeout(load, q ? 300 : 0); // debounce search
    return () => clearTimeout(id);
  }, [load, q]);

  return (
    <main className="min-h-[100dvh] pb-28">
      <OfflineBanner />
      <TopBar
        title={t("nav.leads", "Leads")}
        right={
          <div className="flex items-center gap-1">
            <button
              onClick={() => setAdding(true)}
              aria-label={t("leads.add", "Add lead")}
              className="flex h-10 w-10 items-center justify-center rounded-full text-ink-soft hover:bg-slate-100"
            >
              <Icon name="plus" />
            </button>
            <Link
              href="/bookings"
              aria-label={t("bookings.title", "Bookings")}
              className="flex h-10 w-10 items-center justify-center rounded-full text-ink-soft hover:bg-slate-100"
            >
              <Icon name="clock" />
            </Link>
          </div>
        }
      />

      {adding && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40" onClick={() => setAdding(false)}>
          <div
            className="w-full max-w-md rounded-t-3xl bg-white p-5 pb-8"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="pb-3 text-lg font-semibold">{t("leads.add", "Add lead")}</h2>
            <div className="space-y-3">
              <input
                value={newPhone}
                onChange={(e) => setNewPhone(e.target.value)}
                placeholder={t("leads.addPhone", "WhatsApp number *")}
                inputMode="tel"
                className="w-full rounded-xl border border-slate-200 bg-white py-3 px-4 text-base focus:border-brand"
              />
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={t("leads.addName", "Name")}
                className="w-full rounded-xl border border-slate-200 bg-white py-3 px-4 text-base focus:border-brand"
              />
              <input
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder={t("leads.addNote", "What do they want? (optional)")}
                className="w-full rounded-xl border border-slate-200 bg-white py-3 px-4 text-base focus:border-brand"
              />
              <Button fullWidth loading={saving} disabled={!newPhone.trim()} onClick={addLead}>
                {t("leads.addSave", "Save lead")}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="px-4 pt-3">
        <div className="relative">
          <Icon name="leads" className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-ink-faint" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("leads.search", "Search name or number")}
            aria-label="Search leads"
            className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-base focus:border-brand"
          />
        </div>
      </div>

      {/* Filter tabs */}
      <div className="no-scrollbar flex gap-2 overflow-x-auto px-4 pt-3">
        {filters.map((f, i) => (
          <button
            key={f.key}
            onClick={() => setActive(i)}
            className={`tap !min-h-[40px] shrink-0 !px-4 text-sm ${
              active === i
                ? "bg-brand text-white shadow-brand"
                : "border border-slate-200 bg-white text-ink-soft"
            }`}
          >
            {f.en}
          </button>
        ))}
      </div>

      {/* List */}
      <section className="px-4 pt-4">
        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !leads ? (
          <div className="space-y-2">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : leads.length === 0 ? (
          <EmptyState
            title={t("leads.emptyTitle", "No leads here yet")}
            hint={t(
              "leads.emptyHint",
              "Leads from your ads open in your WhatsApp — log them with + so Saathi can track your results."
            )}
            icon="leads"
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {leads.map((lead) => (
              <li key={lead.id}>
                <Link
                  href={`/leads/${lead.id}`}
                  className="flex items-center justify-between rounded-2xl border border-slate-100 bg-white p-3.5 shadow-card transition hover:shadow-elevated active:scale-[0.99]"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-semibold">
                        {lead.name || t("leads.newEnquiry", "New enquiry")}
                      </span>
                      <ScoreBadge score={lead.score} />
                    </div>
                    <p className="mt-0.5 truncate text-sm text-ink-muted">
                      {lead.intent_summary || lead.status}
                    </p>
                  </div>
                  <Icon name="chevronRight" className="h-5 w-5 shrink-0 text-ink-faint" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <BottomNav active="/leads" />
    </main>
  );
}
