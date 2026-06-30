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
      const [rep, ins, dec] = await Promise.all([
        api.runReport(account),
        api.insights(account),
        api.decisions(account),
      ]);
      setMessage(rep.message);
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
  if (message == null || !insights || !decisions)
    return <Loading label={t("reports.preparing", "Preparing your report…")} />;

  const spend = insights.reduce((s, i) => s + i.spend_paise, 0);
  const leads = insights.reduce((s, i) => s + i.leads, 0);
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
      REQUEST_CREATIVE: t("reports.act.creative", "Refreshing tired ads"),
      REALLOCATE: t("reports.act.realloc", "Moved budget to what works"),
      RESUME: t("reports.act.resume", "Resumed an ad set"),
    } as Record<string, string>
  )[action] || action;
}

function reasonLabel(code: string | null, t: (k: string, f: string) => string): string {
  if (!code) return t("reports.reason.routine", "Routine optimisation");
  return (
    {
      HIGH_CPL: t("reports.reason.highCpl", "It was costing too much per lead"),
      LOW_CTR: t("reports.reason.lowCtr", "Too few people were clicking"),
      WINNER: t("reports.reason.winner", "It was bringing cheap, quality leads"),
      FATIGUE: t("reports.reason.fatigue", "People had seen it too many times"),
    } as Record<string, string>
  )[code] || code.replace(/_/g, " ").toLowerCase();
}
