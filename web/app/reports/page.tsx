"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { Decision, Insight } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  BarChart,
  BottomNav,
  Card,
  ErrorState,
  Icon,
  Loading,
  OfflineBanner,
  SaathiStatusCard,
  Stat,
  TopBar,
} from "@/components/ui";
import { rupees } from "@/lib/format";

export default function Reports() {
  const router = useRouter();
  const t = useT();
  const [message, setMessage] = useState<string | null>(null);
  const [insights, setInsights] = useState<Insight[] | null>(null);
  const [decisions, setDecisions] = useState<Decision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const account = getUser()?.account_id;
    if (!account) return router.replace("/login");
    setError(null);
    try {
      // Stats come from data that already exists; the Saathi summary is the latest
      // nightly REPORT notification. Never POST report/run per visit — in queued mode
      // that returns no message (permanent spinner) and it burns an LLM call per view.
      const [ins, dec, notifs] = await Promise.all([
        api.insights(account),
        api.decisions(account),
        api.notifications(account).catch(() => []),
      ]);
      const latestReport = (notifs as any[]).find((n) => n.kind === "REPORT");
      setMessage(latestReport?.body ?? "");
      setInsights(ins);
      setDecisions(dec);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load your report."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (error && !insights)
    return (
      <main className="min-h-[100dvh]">
        <TopBar title={t("nav.reports", "Reports")} back="/dashboard" />
        <ErrorState message={error} onRetry={load} />
      </main>
    );
  if (!insights || !decisions)
    return <Loading label={t("reports.preparing", "Preparing your report…")} />;

  // Sum ADSET rows only — ACCOUNT rows are rollups of the same money and would double it.
  const adsetRows = insights.filter((i) => i.level === "ADSET");
  const spend = adsetRows.reduce((s, i) => s + i.spend_paise, 0);
  const leads = adsetRows.reduce((s, i) => s + i.leads, 0);
  const cpl = leads ? Math.round(spend / leads) : null;

  const adsets = insights
    .filter((i) => i.level === "ADSET")
    .slice(0, 6)
    .map((i, idx) => ({ label: `#${idx + 1}`, value: Math.round(i.spend_paise / 100) }));

  return (
    <main className="min-h-[100dvh] pb-28">
      <OfflineBanner />
      <TopBar title={t("nav.reports", "Reports")} back="/dashboard" />
      <section className="space-y-4 p-4">
        {message && <SaathiStatusCard line={message} />}

        <div className="grid grid-cols-3 gap-2.5">
          <Stat label={t("reports.spend", "Spend")} value={rupees(spend)} tone="brand" />
          <Stat label={t("reports.leads", "Leads")} value={String(leads)} />
          <Stat label={t("reports.costPerLead", "Cost / lead")} value={cpl != null ? rupees(cpl) : "—"} />
        </div>

        {adsets.length > 0 && (
          <Card>
            <p className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-muted">
              {t("reports.spendByAd", "Spend by ad set (₹)")}
            </p>
            <BarChart data={adsets} />
          </Card>
        )}

        <div>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("reports.whatSaathiDid", "What Saathi did")}
          </h2>
          {decisions.length === 0 ? (
            <Card>
              <p className="text-sm text-ink-muted">
                {t("reports.stillLearning", "No changes yet — Saathi is still learning your leads.")}
              </p>
            </Card>
          ) : (
            <ul className="space-y-2">
              {decisions.map((d, i) => (
                <li key={i}>
                  <Card className="flex items-start gap-3 !p-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand">
                      <Icon name={actionIcon(d.action)} className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-medium">{actionLabel(d.action, t)}</p>
                      <p className="text-sm text-ink-muted">{reasonLabel(d.reason_code, t)}</p>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <BottomNav active="/reports" />
    </main>
  );
}

function actionIcon(action: string): string {
  return (
    {
      PAUSE: "pause",
      SCALE: "reports",
      PROMOTE: "sparkle",
      REQUEST_CREATIVE: "sparkle",
      REALLOCATE: "billing",
      RESUME: "play",
    } as Record<string, string>
  )[action] || "check";
}

function actionLabel(action: string, t: (k: string, f: string) => string): string {
  return (
    {
      PAUSE: t("reports.act.pause", "Paused a weak ad set"),
      SCALE: t("reports.act.scale", "Scaled up a winner"),
      PROMOTE: t("reports.act.promote", "Promoted a winning test ad"),
      REQUEST_CREATIVE: t("reports.act.creative", "Refreshing tired ads"),
      REALLOCATE: t("reports.act.realloc", "Moved budget to what works"),
      RESUME: t("reports.act.resume", "Resumed an ad set"),
    } as Record<string, string>
  )[action] || action;
}

function reasonLabel(code: string | null, t: (k: string, f: string) => string): string {
  if (!code) return "";
  return (
    {
      zero_conversions: t("reports.rZero", "No leads despite spend — stopped it"),
      cpl_over_3x_target: t("reports.rCpl", "Cost per lead too high — stopped it"),
      fatigue_frequency: t("reports.rFatigue", "People saw it too often — made a fresh ad"),
      fatigue_cooldown: t("reports.rCooldown", "Fresh ad already made today"),
      proven_winner: t("reports.rWinner", "Working well — gave it more budget"),
      efficient_scale: t("reports.rEfficient", "Good cost per lead — gave it more budget"),
      test_winner_promoted: t("reports.rPromoted", "Test ad won — promoted it"),
      reallocate_to_winner: t("reports.rRealloc", "Moved budget to the best ad"),
      emergency_daily_cap: t("reports.rEmergency", "Spend hit the safety limit — paused everything"),
      account_budget_cap: t("reports.rBudgetCap", "Held back by your daily budget"),
      held_by_account_budget: t("reports.rBudgetCap", "Held back by your daily budget"),
      auto_recovery_restart: t("reports.rRestart", "Restarted your best ad group"),
      meta_rejected_replacement: t("reports.rRejected", "Meta rejected an ad — made a fresh one"),
      stable: t("reports.rStable", "Running steady"),
    } as Record<string, string>
  )[code] || code.replace(/_/g, " ");
}
