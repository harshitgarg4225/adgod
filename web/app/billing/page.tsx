"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken, getUser } from "@/lib/api";
import type { Invoice, SubscriptionInfo, Tier } from "@/lib/types";
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

// [i18n key, English fallback] so plan features render in the owner's language.
const FEATURES: Record<string, [string, string][]> = {
  STARTER: [
    ["billing.feat.oneCampaign", "1 campaign"],
    ["billing.feat.dailyReport", "Daily WhatsApp report"],
    ["billing.feat.leadInbox", "Lead inbox"],
  ],
  GROWTH: [
    ["billing.feat.ctwaForms", "Click-to-WhatsApp + Lead Forms"],
    ["billing.feat.qualifier", "24×7 WhatsApp qualifier"],
    ["billing.feat.autoOpt", "Auto-optimisation"],
    ["billing.feat.leadCrm", "Lead CRM"],
  ],
  PRO: [
    ["billing.feat.allGrowth", "Everything in Growth"],
    ["billing.feat.multiVideo", "Multi-campaign + video"],
    ["billing.feat.wallet", "Ad wallet"],
    ["billing.feat.csv", "CSV export"],
    ["billing.feat.priority", "Priority support"],
  ],
};

export default function Billing() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [manualMode, setManualMode] = useState(false);
  const [sub, setSub] = useState<SubscriptionInfo | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getUser()?.account_id) return router.replace("/login");
    setError(null);
    try {
      const [tt, s, inv] = await Promise.all([
        api.tiers(),
        api.subscription(),
        api.invoices().catch(() => []),
      ]);
      setTiers(tt.tiers);
      setManualMode(tt.manual_mode);
      setSub(s);
      setInvoices(inv);
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load billing."));
    }
  }, [router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function openInvoice(id: string) {
    try {
      const res = await fetch(api.invoiceDocumentUrl(id), {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      const html = await res.text();
      const w = window.open("", "_blank");
      if (w) {
        w.document.write(html);
        w.document.close();
      }
    } catch {
      toast.show(t("common.somethingWrong", "Could not open invoice."), "error");
    }
  }

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
                {(FEATURES[tier.tier] || []).map(([key, fallback]) => (
                  <li key={key} className="flex items-center gap-2 text-sm text-ink-soft">
                    <Icon name="check" className="h-4 w-4 text-brand" strokeWidth={2.5} />
                    {t(key, fallback)}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-ink-faint">
                {manualMode
                  ? t("billing.manualNote", "Billing is handled by your Salmor manager.")
                  : t("billing.gstTrial", "+ 18% GST · 7-day free trial · cancel anytime")}
              </p>
              <Button
                fullWidth
                variant={active ? "secondary" : popular ? "accent" : "primary"}
                disabled={!!busy || active || manualMode}
                loading={busy === tier.tier}
                className="mt-3"
                onClick={() => subscribe(tier.tier)}
              >
                {active
                  ? t("billing.current", "Current plan")
                  : manualMode
                    ? t("billing.contactManager", "Talk to your manager")
                    : t("billing.choosePlan", "Choose plan")}
              </Button>
            </Card>
          );
        })}

        {/* Wallet + invoices */}
        <Link href="/wallet" className="block">
          <Card className="flex items-center justify-between">
            <span className="flex items-center gap-2 font-semibold">
              <Icon name="billing" className="h-5 w-5 text-brand" /> {t("billing.wallet", "Ad wallet")}
            </span>
            <Icon name="chevronRight" className="text-ink-faint" />
          </Card>
        </Link>

        {invoices.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-muted">
              {t("billing.invoices", "Invoices")}
            </p>
            <ul className="space-y-2">
              {invoices.map((inv) => (
                <li key={inv.id}>
                  <button onClick={() => openInvoice(inv.id)} className="block w-full text-left">
                    <Card className="flex items-center justify-between !p-3">
                      <div>
                        <p className="font-medium">{inv.period || t("billing.invoice", "Invoice")}</p>
                        <p className="text-2xs uppercase text-ink-faint">{inv.status}</p>
                      </div>
                      <span className="text-sm font-semibold">
                        ₹{((inv.amount_paise + inv.gst_paise) / 100).toLocaleString("en-IN")}
                      </span>
                    </Card>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center justify-center gap-2 pt-1 text-xs text-ink-faint">
          <Icon name="shield" className="h-4 w-4" />
          {t("billing.securedRazorpay", "Secured by Razorpay · UPI Autopay")}
        </div>
      </section>
      <BottomNav active="/billing" />
    </main>
  );
}
