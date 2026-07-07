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
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Icon,
  OfflineBanner,
  SaathiAvatar,
  SaathiStatusCard,
  ScoreBadge,
  Sheet,
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
  const [budgetOpen, setBudgetOpen] = useState(false);
  const [budgetDraft, setBudgetDraft] = useState(500);
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [busyPause, setBusyPause] = useState(false);
  const [actingAs, setActingAs] = useState<string | null>(null);
  const [needsConnect, setNeedsConnect] = useState(false);

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
      // Pre-launch accounts may still owe us the lead destination — surface the
      // one next action instead of a dead dashboard.
      if (["SIGNED_UP", "ONBOARDING"].includes(h.phase)) {
        try {
          const st = await api.onboardingStatus();
          setNeedsConnect(!!st.missing_steps?.includes("whatsapp_connection"));
        } catch {
          /* keep dashboard usable */
        }
      }
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

        {/* Proof of work: once live, the owner can SEE their ads. */}
        {home && ["LIVE", "OPTIMIZING", "FATIGUE_REFRESH", "PAUSED"].includes(home.phase) && (
          <Link
            href="/ads"
            className="flex items-center justify-between rounded-2xl border border-slate-100 bg-white p-4 shadow-card transition active:scale-[0.99]"
          >
            <div className="flex items-center gap-3">
              <Icon name="sparkle" className="h-6 w-6 text-brand" />
              <p className="font-semibold">{t("dashboard.seeMyAds", "See my ads")}</p>
            </div>
            <Icon name="chevronLeft" className="h-5 w-5 rotate-180 text-ink-faint" />
          </Link>
        )}

        {/* Setup phases: a provisioned owner lands here with a business profile but may
            still owe the lead destination. One clear next action — never a dead end. */}
        {home && ["SIGNED_UP", "ONBOARDING"].includes(home.phase) && (
          needsConnect ? (
            <Link
              href="/onboarding/connect"
              className="block rounded-2xl bg-brand p-4 text-white shadow-brand transition active:scale-[0.99]"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-bold">
                    {t("dashboard.connectCtaTitle", "One step left: where should customers reach you?")}
                  </p>
                  <p className="mt-0.5 text-sm text-white/85">
                    {t("dashboard.connectCtaHint", "WhatsApp, phone calls — you choose")}
                  </p>
                </div>
                <Icon name="chevronLeft" className="h-6 w-6 shrink-0 rotate-180" />
              </div>
            </Link>
          ) : (
            <div className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-card">
              <Icon name="sparkle" className="h-6 w-6 shrink-0 text-brand" />
              <p className="text-sm text-ink-soft">
                {t(
                  "dashboard.preparing",
                  "Saathi is preparing your ads — you'll see them here for review. Nothing needed from you right now."
                )}
              </p>
            </div>
          )
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
                  <Stat label={t("dashboard.leadsToday", "Leads today")} value={String(home.enquiries_today)} />
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

            {/* Spend trend + THE one control: the daily budget, one tap from home */}
            {home && (
              <Card className="flex items-center justify-between">
                <button className="text-left" onClick={() => {
                  setBudgetDraft(Math.round(home.daily_budget_paise / 100) || 500);
                  setBudgetOpen(true);
                }}>
                  <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                    {t("dashboard.spend7d", "Last 7 days")}
                  </p>
                  <p className="mt-0.5 text-sm text-ink-muted">
                    {t("dashboard.dailyCap", "Daily cap")}{" "}
                    <span className="font-semibold text-ink">{home.daily_budget_display}</span>{" "}
                    <span className="font-medium text-brand">{t("dashboard.change", "Change")}</span>
                  </p>
                </button>
                {home.spend_trend?.some((v) => v > 0) ? (
                  <Sparkline points={home.spend_trend.map((p) => p / 100)} />
                ) : (
                  <span className="text-xs text-ink-faint">{t("dashboard.noSpendYet", "No spend yet")}</span>
                )}
              </Card>
            )}

            {/* Owner kill-switch — only where ads actually exist to pause. A pre-launch
                "Ads are running" toggle is a lie and pausing then wedges the pipeline. */}
            {home && ["LIVE", "OPTIMIZING", "FATIGUE_REFRESH", "PAUSED"].includes(home.phase) && (
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

      <Sheet open={budgetOpen} onClose={() => setBudgetOpen(false)}
        title={t("dashboard.changeBudget", "Daily budget")}>
        <div className="space-y-4">
          <p className="text-center text-3xl font-bold">₹{budgetDraft.toLocaleString("en-IN")}
            <span className="text-base font-medium text-ink-muted">/{t("billing.day", "day")}</span>
          </p>
          <input
            type="range" min={100} max={5000} step={100} value={budgetDraft}
            onChange={(e) => setBudgetDraft(Number(e.target.value))}
            className="w-full accent-[var(--brand,#16a34a)]"
            aria-label={t("dashboard.changeBudget", "Daily budget")}
          />
          <p className="text-center text-xs text-ink-muted">
            {t("dashboard.budgetSafety", "Saathi never spends more than this in a day.")}
          </p>
          <Button fullWidth loading={budgetSaving} onClick={async () => {
            const account = getUser()?.account_id;
            if (!account) return;
            setBudgetSaving(true);
            try {
              // Server pushes the change to the LIVE Meta ad sets immediately.
              await api.updateSettings(account, { daily_budget_paise: budgetDraft * 100 });
              setBudgetOpen(false);
              await load();
              toast.show(t("settings.savedBudget", "Budget updated."), "success");
            } catch (e: any) {
              toast.show(e.userMessage || t("common.somethingWrong", "Could not update."), "error");
            } finally {
              setBudgetSaving(false);
            }
          }}>
            {t("common.save", "Save")}
          </Button>
        </div>
      </Sheet>

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
