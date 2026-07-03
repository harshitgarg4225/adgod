"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, exitClient, getActingAs, getUser } from "@/lib/api";
import type { Home, LeadListItem } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  ActingAsBanner,
  BottomNav,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Icon,
  OfflineBanner,
  SaathiAvatar,
  SaathiStatusCard,
  ScoreBadge,
  Skeleton,
  SkeletonCard,
  Sparkline,
  Stat,
  Switch,
  useToast,
} from "@/components/ui";

export default function Dashboard() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [home, setHome] = useState<Home | null>(null);
  const [leads, setLeads] = useState<LeadListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmPause, setConfirmPause] = useState(false);
  const [busyPause, setBusyPause] = useState(false);
  const [actingAs, setActingAs] = useState<string | null>(null);

  useEffect(() => {
    setActingAs(getActingAs());
  }, []);

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
      setError(e.userMessage || t("common.somethingWrong", "Could not load your dashboard."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function togglePause(next: boolean) {
    const user = getUser();
    if (!user?.account_id || !home) return;
    setBusyPause(true);
    try {
      const r = next
        ? await api.pauseAccount(user.account_id)
        : await api.resumeAccount(user.account_id);
      setHome({ ...home, paused: r.paused, phase: r.phase });
      toast.show(
        next
          ? t("dashboard.pausedToast", "Ads paused. You're in control.")
          : t("dashboard.resumedToast", "Ads resumed — Saathi is back on it. 🎉"),
        next ? "info" : "success"
      );
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Something went wrong."), "error");
    } finally {
      setBusyPause(false);
      setConfirmPause(false);
    }
  }

  const name = getUser()?.name || t("dashboard.owner", "Owner");

  return (
    <main className="min-h-[100dvh] pb-28">
      {actingAs && (
        <ActingAsBanner
          name={actingAs}
          onExit={() => {
            exitClient();
            router.replace("/partner");
          }}
        />
      )}
      <OfflineBanner />

      {/* Header */}
      <header className="bg-gradient-to-br from-brand to-brand-700 px-5 pb-6 pt-5 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SaathiAvatar size={40} />
            <div>
              <p className="text-sm text-white/80">{t("dashboard.greeting", "Namaste")} 👋</p>
              <h1 className="text-xl font-bold leading-tight">{name}</h1>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Link
              href="/notifications"
              aria-label="Notifications"
              className="relative flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10"
            >
              <Icon name="bell" />
              {!!home?.unread_notifications && (
                <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-2xs font-bold">
                  {home.unread_notifications}
                </span>
              )}
            </Link>
            <Link
              href="/settings"
              aria-label="Settings"
              className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10"
            >
              <Icon name="settings" />
            </Link>
          </div>
        </div>
      </header>

      {/* Saathi status + spend safety */}
      <section className="-mt-4 space-y-3 px-4">
        {home ? (
          <SaathiStatusCard line={home.saathi_status} />
        ) : (
          <Skeleton className="h-16 w-full rounded-2xl" />
        )}

        {/* The one human gate on the ASSISTED path: without this card a provisioned
            owner has NO route to the approval screen and the launch stalls forever. */}
        {home && ["PENDING_APPROVAL", "CREATIVE_GENERATED", "RESEARCHED"].includes(home.phase) && (
          <Link
            href="/onboarding/creatives"
            className="block rounded-2xl bg-brand p-4 text-white shadow-brand transition active:scale-[0.99]"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold">
                  {t("dashboard.approveCtaTitle", "Your ads are ready to review")}
                </p>
                <p className="mt-0.5 text-sm text-white/85">
                  {t("dashboard.approveCtaHint", "Tap to approve them and go live")}
                </p>
              </div>
              <Icon name="play" className="h-7 w-7 shrink-0" />
            </div>
          </Link>
        )}

        {error && !home ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2.5">
              {home ? (
                <>
                  <Stat label={t("dashboard.spentToday", "Spent today")} value={home.today_spend_display} tone="brand" />
                  <Stat label={t("dashboard.leadsToday", "Leads today")} value={String(home.qualified_today)} />
                  <Stat
                    label={t("dashboard.costPerLead", "Cost / lead")}
                    value={home.cpql_display || "—"}
                  />
                </>
              ) : (
                <>
                  <SkeletonCard />
                  <SkeletonCard />
                  <SkeletonCard />
                </>
              )}
            </div>

            {/* Spend trend + budget safety */}
            {home && (
              <Card className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                    {t("dashboard.spend7d", "Last 7 days")}
                  </p>
                  <p className="mt-0.5 text-sm text-ink-muted">
                    {t("dashboard.dailyCap", "Daily cap")} {home.daily_budget_display}
                  </p>
                </div>
                {home.spend_trend?.some((v) => v > 0) ? (
                  <Sparkline points={home.spend_trend.map((p) => p / 100)} />
                ) : (
                  <span className="text-xs text-ink-faint">{t("dashboard.noSpendYet", "No spend yet")}</span>
                )}
              </Card>
            )}

            {/* Owner kill-switch */}
            {home && (
              <Card className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Icon name="shield" className="h-6 w-6 text-brand" />
                  <div>
                    <p className="font-semibold">
                      {home.paused
                        ? t("dashboard.adsPaused", "Ads are paused")
                        : t("dashboard.adsRunning", "Ads are running")}
                    </p>
                    <p className="text-xs text-ink-muted">
                      {t("dashboard.youControl", "You're always in control of spend.")}
                    </p>
                  </div>
                </div>
                <Switch
                  checked={!home.paused}
                  label="Toggle ads"
                  onChange={(next) => {
                    if (!next) setConfirmPause(true);
                    else togglePause(false);
                  }}
                />
              </Card>
            )}
          </>
        )}
      </section>

      {/* Leads */}
      <section className="px-4 pt-5">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("dashboard.recentLeads", "Recent leads")}
          </h2>
          <Link href="/leads" className="text-sm font-semibold text-brand">
            {t("common.seeAll", "See all")}
          </Link>
        </div>
        {error && !leads ? (
          <p className="rounded-xl bg-slate-50 p-3 text-sm text-ink-muted">
            {t("dashboard.leadsUnavailable", "Couldn't load leads — pull to retry.")}
          </p>
        ) : !leads ? (
          <div className="space-y-2">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : leads.length === 0 ? (
          <EmptyState
            title={t("dashboard.noLeadsTitle", "No leads yet")}
            hint={
              home && ["LIVE", "OPTIMIZING"].includes(home.phase)
                ? t("dashboard.noLeads", "Your ads are live — your first lead will appear here soon.")
                : t("dashboard.noLeadsPrelaunch", "Once your ads go live, leads will appear here.")
            }
            icon="leads"
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {leads.slice(0, 6).map((lead) => (
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

      <ConfirmDialog
        open={confirmPause}
        title={t("dashboard.pauseConfirmTitle", "Pause all ads?")}
        body={t(
          "dashboard.pauseConfirmBody",
          "Saathi will stop spending immediately. You can resume anytime — no money is lost."
        )}
        confirmLabel={busyPause ? t("common.saving", "Pausing…") : t("dashboard.pauseAds", "Pause ads")}
        tone="danger"
        onConfirm={() => togglePause(true)}
        onClose={() => setConfirmPause(false)}
      />

      <BottomNav active="/dashboard" />
    </main>
  );
}
