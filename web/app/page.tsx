"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getUser } from "@/lib/api";
import { PRICING, TRIAL_DAYS } from "@/lib/company";
import { useI18n } from "@/lib/i18n";
import { Button, Icon, SaathiAvatar } from "@/components/ui";
import { PublicFooter, PublicHeader } from "@/components/public";

/**
 * Public landing page — the storefront a prospect (or a Razorpay/Meta reviewer) sees.
 * Logged-in users skip it and go straight to their dashboard, so the app still opens
 * app-like from the home-screen icon.
 */
export default function Landing() {
  const router = useRouter();
  const { t } = useI18n();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (getUser()) router.replace("/dashboard");
    else setChecked(true);
  }, [router]);

  if (!checked) {
    // Branded splash so a cold start over a slow network isn't a blank white screen.
    return (
      <main className="flex min-h-[100dvh] flex-col items-center justify-center gap-4">
        <SaathiAvatar size={80} className="animate-pop" />
        <p className="text-2xl font-bold tracking-tight">Salmor</p>
        <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent" />
      </main>
    );
  }

  const steps = [
    {
      icon: "mic",
      title: t("landing.step1Title", "Tell Saathi about your business"),
      body: t("landing.step1Body", "5 minutes, in your language. What you sell, your area, your budget."),
    },
    {
      icon: "sparkle",
      title: t("landing.step2Title", "Saathi makes & runs your ads"),
      body: t(
        "landing.step2Body",
        "Ad copy, images and targeting on Facebook & Instagram — created, launched and improved daily, automatically."
      ),
    },
    {
      icon: "whatsapp",
      title: t("landing.step3Title", "Leads arrive on WhatsApp"),
      body: t(
        "landing.step3Body",
        "Every interested customer lands in your inbox — greeted, qualified and rated Hot / Warm / Cold for you."
      ),
    },
  ];

  const features = [
    { icon: "shield", text: t("landing.feat1", "You approve before anything goes live — and can pause ads any time") },
    { icon: "reports", text: t("landing.feat2", "Daily WhatsApp report: spend, leads, cost per lead — no dashboards needed") },
    { icon: "billing", text: t("landing.feat3", "Your ad budget stays in YOUR ad account. We never touch it") },
    { icon: "leads", text: t("landing.feat4", "Works in English, हिन्दी and ਪੰਜਾਬੀ") },
  ];

  const tierNames: Record<string, string> = {
    STARTER: t("landing.tierStarter", "Starter"),
    GROWTH: t("landing.tierGrowth", "Growth"),
    PRO: t("landing.tierPro", "Pro"),
  };
  const tierDescs: Record<string, string> = {
    STARTER: t("landing.tierStarterDesc", "One campaign running, leads qualified on WhatsApp."),
    GROWTH: t("landing.tierGrowthDesc", "More campaigns, auto-optimisation and booking flows."),
    PRO: t("landing.tierProDesc", "Everything, plus wallet, exports and priority support."),
  };

  return (
    <main className="min-h-[100dvh]">
      <PublicHeader />

      {/* Hero */}
      <section className="px-6 pb-10 pt-8 text-center">
        <SaathiAvatar size={72} className="mx-auto animate-pop drop-shadow" />
        <h1 className="mx-auto mt-5 max-w-md text-3xl font-bold leading-tight tracking-tight deva">
          {t("landing.heroTitle", "Ads that bring customers. Without learning ads.")}
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-ink-muted deva">
          {t(
            "landing.heroSub",
            "Saathi — your AI helper — runs your Facebook & Instagram ads and talks to every lead on WhatsApp, so you only meet customers who are ready."
          )}
        </p>
        <div className="mt-6 flex flex-col items-center gap-3">
          <Link href="/login" className="w-full max-w-xs">
            <Button fullWidth size="lg">
              {t("landing.cta", "Start free — 7 days")}
            </Button>
          </Link>
          <p className="text-2xs text-ink-faint deva">
            {t("landing.ctaHint", "No card needed to start. Cancel anytime.")}
          </p>
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 py-8">
        <h2 className="text-center text-xl font-bold tracking-tight deva">
          {t("landing.howTitle", "How it works")}
        </h2>
        <ol className="mx-auto mt-6 flex max-w-md flex-col gap-4">
          {steps.map((s, i) => (
            <li key={s.title} className="flex items-start gap-4 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-light text-brand">
                <Icon name={s.icon} className="h-5 w-5" />
              </span>
              <div>
                <p className="font-semibold deva">
                  {i + 1}. {s.title}
                </p>
                <p className="mt-1 text-sm text-ink-muted deva">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* Trust points */}
      <section className="px-6 py-8">
        <ul className="mx-auto flex max-w-md flex-col gap-3">
          {features.map((f) => (
            <li key={f.text} className="flex items-center gap-3 text-sm text-ink-soft deva">
              <Icon name={f.icon} className="h-5 w-5 shrink-0 text-brand" />
              {f.text}
            </li>
          ))}
        </ul>
      </section>

      {/* Pricing — visible pricing is required for payment-gateway activation. */}
      <section id="pricing" className="px-6 py-8">
        <h2 className="text-center text-xl font-bold tracking-tight deva">
          {t("landing.pricingTitle", "Simple monthly pricing")}
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-center text-sm text-ink-muted deva">
          {t(
            "landing.pricingSub",
            "Platform fee only. Your ad budget is separate, stays in your own ad account, and is always in your control."
          )}
        </p>
        <div className="mx-auto mt-6 flex max-w-md flex-col gap-4">
          {PRICING.map((p) => (
            <div
              key={p.tier}
              className={`rounded-2xl border p-5 ${
                p.tier === "GROWTH" ? "border-brand bg-brand-50" : "border-slate-100 bg-white"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <p className="font-semibold">{tierNames[p.tier]}</p>
                {p.tier === "GROWTH" && (
                  <span className="rounded-full bg-brand px-2.5 py-0.5 text-2xs font-semibold text-white">
                    {t("landing.popular", "Most popular")}
                  </span>
                )}
              </div>
              <p className="mt-2 text-2xl font-bold">
                ₹{p.priceInr.toLocaleString("en-IN")}
                <span className="text-sm font-medium text-ink-muted">
                  {t("landing.perMonth", "/month + GST")}
                </span>
              </p>
              <p className="mt-2 text-sm text-ink-muted deva">{tierDescs[p.tier]}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-xs text-ink-faint deva">
          {t("landing.trialNote", `Every plan starts with a ${TRIAL_DAYS}-day free trial.`)}
        </p>
      </section>

      {/* Final CTA */}
      <section className="px-6 py-8 text-center">
        <Link href="/login" className="mx-auto block w-full max-w-xs">
          <Button fullWidth size="lg">
            {t("landing.ctaBottom", "Get my first leads")}
          </Button>
        </Link>
      </section>

      <PublicFooter />
    </main>
  );
}
