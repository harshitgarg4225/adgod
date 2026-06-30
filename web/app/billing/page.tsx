"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import type { SubscriptionInfo, Tier } from "@/lib/types";
import { useT } from "@/lib/i18n";
import {
  Badge,
  BottomNav,
  Button,
  Card,
  ErrorState,
  Icon,
  Loading,
  OfflineBanner,
  TopBar,
  useToast,
} from "@/components/ui";

const FEATURES: Record<string, string[]> = {
  STARTER: ["1 campaign", "Daily WhatsApp report", "Lead inbox"],
  GROWTH: ["Click-to-WhatsApp + Lead Forms", "24×7 WhatsApp qualifier", "Auto-optimisation", "Lead CRM"],
  PRO: ["Everything in Growth", "Multi-campaign + video", "Ad wallet", "CSV export", "Priority support"],
};

export default function Billing() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getUser()?.account_id) return router.replace("/login");
    setError(null);
    try {
      const [tt, s] = await Promise.all([api.tiers(), api.subscription()]);
      setTiers(tt);
      setSub(s);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load billing."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function subscribe(tier: string) {
    setBusy(tier);
    try {
      const r = await api.subscribe(tier);
      if (r.mandate_url) {
        window.location.href = r.mandate_url;
      } else {
        toast.show(t("billing.activated", "Plan activated. Welcome aboard! 🎉"));
        await load();
        setBusy(null);
      }
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not start subscription."), "error");
      setBusy(null);
    }
  }

  if (error && !tiers)
    return (
      <main className="min-h-[100dvh]">
        <TopBar title={t("nav.billing", "Plans & billing")} back="/dashboard" />
        <ErrorState message={error} onRetry={load} />
      </main>
    );
  if (!tiers || !sub) return <Loading label={t("common.loading", "Loading…")} />;

  return (
    <main className="min-h-[100dvh] pb-28">
      <OfflineBanner />
      <TopBar title={t("nav.billing", "Plans & billing")} back="/dashboard" />
      <section className="space-y-3 p-4">
        {sub.status !== "NONE" && (
          <Card className="flex items-center justify-between !bg-brand-50">
            <div>
              <p className="text-sm text-ink-muted">{t("billing.currentPlan", "Current plan")}</p>
              <p className="font-bold">
                {sub.tier} · {sub.status}
              </p>
              {sub.trial_end && (
                <p className="text-xs text-ink-muted">
                  {t("billing.trialEnds", "Trial ends")}{" "}
                  {new Date(sub.trial_end).toLocaleDateString("en-IN")}
                </p>
              )}
            </div>
            <Icon name="check" className="h-7 w-7 text-brand" />
          </Card>
        )}

        {tiers.map((tier, idx) => {
          const active = sub.tier === tier.tier;
          const popular = tier.tier === "GROWTH";
          return (
            <Card
              key={tier.tier}
              className={`relative ${active ? "!border-brand ring-1 ring-brand" : popular ? "!border-accent-200" : ""}`}
            >
              {popular && !active && (
                <div className="absolute -top-2.5 right-4">
                  <Badge tone="accent">{t("billing.popular", "Most popular")}</Badge>
                </div>
              )}
              <div className="flex items-baseline justify-between">
                <h2 className="text-lg font-bold">{tier.tier}</h2>
                <div className="text-right">
                  <span className="text-xl font-bold">{tier.price_display}</span>
                  <span className="text-sm text-ink-muted">/{t("billing.mo", "mo")}</span>
                </div>
              </div>
              <ul className="mt-3 space-y-1.5">
                {(FEATURES[tier.tier] || []).map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-ink-soft">
                    <Icon name="check" className="h-4 w-4 text-brand" strokeWidth={2.5} />
                    {f}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-ink-faint">
                {t("billing.gstTrial", "incl. 18% GST · 7-day free trial · cancel anytime")}
              </p>
              <Button
                fullWidth
                variant={active ? "secondary" : popular ? "accent" : "primary"}
                disabled={!!busy || active}
                loading={busy === tier.tier}
                className="mt-3"
                onClick={() => subscribe(tier.tier)}
              >
                {active
                  ? t("billing.current", "Current plan")
                  : t("billing.choosePlan", "Choose plan")}
              </Button>
            </Card>
          );
        })}

        <div className="flex items-center justify-center gap-2 pt-1 text-xs text-ink-faint">
          <Icon name="shield" className="h-4 w-4" />
          {t("billing.securedRazorpay", "Secured by Razorpay · UPI Autopay")}
        </div>
      </section>
      <BottomNav active="/billing" />
    </main>
  );
}
