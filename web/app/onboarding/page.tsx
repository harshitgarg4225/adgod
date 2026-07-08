"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AdStyle } from "@/lib/types";
import { Button, Icon, Input, TopBar, Textarea, useToast } from "@/components/ui";

const CATEGORIES = [
  "coaching", "clinic", "gym", "salon", "real_estate", "interior",
  "education_consultant", "healthcare", "other",
];
const BUDGETS = [30000, 50000, 100000]; // paise: ₹300 / ₹500 / ₹1,000
const CPQL_GOALS = [10000, 20000, 40000, 80000]; // paise: ₹100 / ₹200 / ₹400 / ₹800 per lead

export default function Onboarding() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    business_name: "",
    category: "coaching",
    offer: "",
    city: "",
    radius_km: 10,
    daily_budget_paise: 50000,
    target_cpql_paise: 20000,
    // Save the account default in the language the owner picked at login, not a
    // hardcoded default — otherwise a Punjabi/English owner gets Hindi server copy.
    language: locale,
    // "What kind of ad" — pre-set to auto so a non-tech owner can just tap through.
    ad_style: "auto",
  });
  const [styles, setStyles] = useState<AdStyle[] | null>(null);

  // Ad-style templates, localized to the UI language the owner picked at login.
  useEffect(() => {
    api.adStyles(locale).then((r) => setStyles(r.styles)).catch(() => setStyles(null));
  }, [locale]);

  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));
  const steps = [
    t("ob.step.business", "Business"),
    t("ob.step.offer", "Offer"),
    t("ob.step.area", "Area"),
    t("ob.step.budget", "Budget"),
    t("ob.step.goal", "Goal"),
    t("ob.step.style", "Ad style"),
  ];

  // Per-step validation gates "Next". The style step is always valid (auto is preset).
  const valid = [
    form.business_name.trim().length >= 2,
    form.offer.trim().length >= 5,
    form.city.trim().length >= 2,
    form.daily_budget_paise > 0,
    form.target_cpql_paise > 0,
    true,
  ][step];

  async function finish() {
    setBusy(true);
    try {
      await api.setBusiness(form);
      router.replace("/onboarding/connect");
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not save."), "error");
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] pb-28">
      {/* Steps are component state on one route: history-back would exit the app and
          discard the form. Render our own step-back control instead. */}
      <TopBar
        title={t("ob.title", "Let's set up your ads")}
        right={
          step > 0 ? (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="flex h-10 items-center rounded-full px-3 text-sm font-medium text-ink-soft hover:bg-slate-100"
            >
              {t("ob.back", "Back")}
            </button>
          ) : undefined
        }
      />
      <div className="px-5 pt-2">
        {/* Progress */}
        <div className="mb-1 flex gap-1.5">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full transition-all ${i <= step ? "bg-brand" : "bg-slate-200"}`}
            />
          ))}
        </div>
        <p className="mb-5 text-sm text-ink-faint">
          {t("ob.stepOf", "Step {n} of {total}", { n: step + 1, total: steps.length })} · {steps[step]}
        </p>

        {step === 0 && (
          <Field
            title={t("ob.q.business", "What's your business name?")}
            sub={t("ob.encourage.business", "We'll use this in your ads and WhatsApp replies.")}
          >
            <Input
              name="business_name"
              voice
              value={form.business_name}
              onChange={(e) => set("business_name", e.target.value)}
              placeholder={t("ob.ph.business", "e.g. Sharma NEET Classes")}
            />
            <Picker options={CATEGORIES} value={form.category} onChange={(v) => set("category", v)} />
          </Field>
        )}

        {step === 1 && (
          <Field
            title={t("ob.q.offer", "What do you sell?")}
            sub={t("ob.encourage.offer", "Tell Saathi in your own words — tap the mic to speak.")}
          >
            <Textarea
              name="offer"
              voice
              rows={4}
              value={form.offer}
              onChange={(e) => set("offer", e.target.value)}
              placeholder={t("ob.ph.offer", "e.g. NEET coaching with small batches and weekly tests")}
            />
          </Field>
        )}

        {step === 2 && (
          <Field
            title={t("ob.q.area", "Which area do you serve?")}
            sub={t("ob.encourage.area", "We'll show ads to people nearby.")}
          >
            <Input
              name="city"
              voice
              value={form.city}
              onChange={(e) => set("city", e.target.value)}
              placeholder={t("ob.ph.city", "e.g. Indore")}
            />
            <label className="mt-3 block text-sm font-medium text-ink-soft">
              {t("ob.radius", "Radius")}: {form.radius_km} km
            </label>
            <input
              type="range"
              min={2}
              max={50}
              value={form.radius_km}
              aria-label="Service radius in km"
              onChange={(e) => set("radius_km", Number(e.target.value))}
              className="w-full accent-brand"
            />
          </Field>
        )}

        {step === 3 && (
          <Field
            title={t("ob.q.budget", "Daily ad budget")}
            sub={t("ob.encourage.budget", "Start small — you can change this anytime.")}
          >
            <div className="grid grid-cols-3 gap-2">
              {BUDGETS.map((b) => (
                <button
                  key={b}
                  onClick={() => set("daily_budget_paise", b)}
                  className={`tap font-semibold ${
                    form.daily_budget_paise === b ? "bg-brand text-white shadow-brand" : "border border-slate-200 bg-white"
                  }`}
                >
                  ₹{b / 100}
                </button>
              ))}
            </div>
            <div className="mt-4 flex items-start gap-2 rounded-xl bg-brand-50 p-3 text-sm text-brand-800">
              <Icon name="shield" className="mt-0.5 h-5 w-5 shrink-0" />
              <span>
                {t(
                  "ob.budgetSafety",
                  "Nothing is charged until your ads go live, and you can pause spending anytime."
                )}
              </span>
            </div>
          </Field>
        )}

        {step === 4 && (
          <Field
            title={t("ob.q.goal", "What's a good lead worth to you?")}
            sub={t("ob.encourage.goal", "Saathi keeps your cost per lead under this — chasing cheaper, better leads.")}
          >
            <div className="grid grid-cols-2 gap-2">
              {CPQL_GOALS.map((g) => (
                <button
                  key={g}
                  onClick={() => set("target_cpql_paise", g)}
                  className={`tap font-semibold ${
                    form.target_cpql_paise === g ? "bg-brand text-white shadow-brand" : "border border-slate-200 bg-white"
                  }`}
                >
                  {t("ob.perLead", "≤ ₹{n}/lead").replace("{n}", String(g / 100))}
                </button>
              ))}
            </div>
          </Field>
        )}

        {step === 5 && (
          <Field
            title={t("ob.q.style", "What kind of ad do you want?")}
            sub={t("ob.encourage.style", "Pick a style — or let Saathi choose. You can change this anytime.")}
          >
            {styles ? (
              <div className="space-y-2">
                {styles.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => set("ad_style", s.key)}
                    className={`flex w-full items-start gap-3 rounded-2xl border p-3 text-left transition active:scale-[0.99] ${
                      form.ad_style === s.key ? "border-brand bg-brand-50 ring-1 ring-brand" : "border-slate-200 bg-white"
                    }`}
                  >
                    <span className="text-2xl leading-none">{s.emoji}</span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2 font-semibold">
                        {s.label}
                        {s.recommended && (
                          <span className="rounded-full bg-brand/10 px-2 py-0.5 text-2xs font-semibold text-brand">
                            {t("ob.recommended", "Recommended")}
                          </span>
                        )}
                      </span>
                      <span className="mt-0.5 block text-sm text-ink-muted">{s.desc}</span>
                    </span>
                    {form.ad_style === s.key && <Icon name="check" className="mt-1 h-5 w-5 shrink-0 text-brand" />}
                  </button>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-16 animate-pulse rounded-2xl bg-slate-100" />
                ))}
              </div>
            )}
          </Field>
        )}
      </div>

      <div className="cta-dock flex gap-2">
        {step < steps.length - 1 ? (
          <Button fullWidth size="lg" disabled={!valid} onClick={() => setStep((s) => s + 1)}>
            {t("common.continue", "Continue")}
          </Button>
        ) : (
          <Button fullWidth size="lg" leftIcon="sparkle" disabled={!valid} loading={busy} onClick={finish}>
            {busy ? t("ob.researching", "Saathi is researching…") : t("ob.create", "Create my ads")}
          </Button>
        )}
      </div>
    </main>
  );
}

function Field({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="animate-slide-up">
      <h2 className="text-xl font-bold">{title}</h2>
      {sub && <p className="mb-4 mt-1 text-sm text-ink-muted">{sub}</p>}
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Picker({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={`min-h-[40px] rounded-full px-4 text-sm font-medium capitalize ${
            value === o ? "bg-brand text-white" : "border border-slate-200 bg-white text-ink-soft"
          }`}
        >
          {o.replace(/_/g, " ")}
        </button>
      ))}
    </div>
  );
}
