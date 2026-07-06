"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearSession, getUser } from "@/lib/api";
import type { Settings } from "@/lib/types";
import { LANGUAGES, useI18n } from "@/lib/i18n";
import {
  BottomNav,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  Icon,
  Input,
  Loading,
  OfflineBanner,
  Sheet,
  TopBar,
  Textarea,
  useToast,
} from "@/components/ui";

// Owner language, not engineer language. ASSISTED = autopilot with a veto window
// (ads self-launch after a few hours unless the owner intervenes); MANUAL = wait for
// the owner forever. FULL (auto-approve immediately) is earned via trust, not chosen here.
const AUTOPILOT: { value: string; en: string; desc: string }[] = [
  {
    value: "ASSISTED",
    en: "Saathi launches automatically",
    desc: "You get a few hours to review new ads — then Saathi launches them for you.",
  },
  {
    value: "MANUAL",
    en: "Ask me first",
    desc: "Nothing goes live until you tap Approve.",
  },
];

export default function SettingsPage() {
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const toast = useToast();
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Editable form state
  const [name, setName] = useState("");
  const [offer, setOffer] = useState("");
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState(500);
  const [gstin, setGstin] = useState("");
  const [legalName, setLegalName] = useState("");
  const [billingAddress, setBillingAddress] = useState("");

  const acc = getUser()?.account_id;

  const load = useCallback(async () => {
    if (!acc) {
      router.replace("/login");
      return;
    }
    setError(null);
    try {
      const data = await api.settings(acc);
      setS(data);
      setName(data.business_name);
      setOffer(data.offer || "");
      setCity(data.service_area_city || "");
      setBudget(Math.round(data.daily_budget_paise / 100) || 500);
      setGstin(data.gstin || "");
      setLegalName(data.legal_name || "");
      setBillingAddress(data.billing_address || "");
    } catch (e: any) {
      setError(e.userMessage || t("common.somethingWrong", "Could not load settings."));
    }
  }, [acc, router, t]);

  useEffect(() => {
    load();
  }, [load]);

  async function save(patch: Record<string, unknown>, successMsg: string) {
    if (!acc) return;
    setBusy(true);
    try {
      const next = await api.updateSettings(acc, patch as any);
      setS(next);
      toast.show(successMsg);
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not save."), "error");
    } finally {
      setBusy(false);
    }
  }

  if (error && !s) {
    return (
      <main className="min-h-[100dvh]">
        <TopBar title={t("settings.title", "Settings")} back="/dashboard" />
        <ErrorState message={error} onRetry={load} />
      </main>
    );
  }
  if (!s) return <Loading label={t("common.loading", "Loading…")} />;

  return (
    <main className="min-h-[100dvh] pb-28">
      <OfflineBanner />
      <TopBar title={t("settings.title", "Settings")} back="/dashboard" />

      <div className="space-y-4 px-4 pt-4">
        {/* Business */}
        <Card className="space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.business", "Business details")}
          </h2>
          <Input
            label={t("settings.businessName", "Business name")}
            value={name}
            voice
            onChange={(e) => setName(e.target.value)}
          />
          <Textarea
            label={t("settings.offer", "What you offer")}
            value={offer}
            voice
            rows={3}
            onChange={(e) => setOffer(e.target.value)}
          />
          <Input
            label={t("settings.city", "City / service area")}
            value={city}
            voice
            onChange={(e) => setCity(e.target.value)}
          />
          <Button
            loading={busy}
            onClick={() =>
              save(
                { business_name: name, offer, service_area_city: city },
                t("settings.savedBusiness", "Business details saved.")
              )
            }
          >
            {t("common.save", "Save")}
          </Button>
        </Card>

        {/* Budget */}
        <Card className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.budget", "Daily budget")}
          </h2>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold text-brand">₹{budget.toLocaleString("en-IN")}</span>
            <span className="text-sm text-ink-muted">{t("settings.perDay", "per day")}</span>
          </div>
          <input
            type="range"
            min={100}
            max={5000}
            step={100}
            value={budget}
            aria-label="Daily budget"
            onChange={(e) => setBudget(Number(e.target.value))}
            className="w-full accent-brand"
          />
          <Button
            variant="secondary"
            loading={busy}
            onClick={() =>
              save(
                { daily_budget_paise: budget * 100 },
                t("settings.savedBudget", "Budget updated.")
              )
            }
          >
            {t("settings.updateBudget", "Update budget")}
          </Button>
          <div className="flex items-center justify-between border-t border-slate-100 pt-2 text-sm">
            <span className="text-ink-muted">{t("settings.thisMonth", "Spent this month")}</span>
            <span className="font-semibold">
              {s.monthly_spend_display}
              {s.monthly_cap_paise
                ? ` / ${Math.round(s.monthly_cap_paise / 100).toLocaleString("en-IN")}`
                : ""}
            </span>
          </div>
        </Card>

        {/* Billing details (GST) */}
        <Card className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.billingDetails", "Billing details (for GST invoices)")}
          </h2>
          <Input label="GSTIN" value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} placeholder="22AAAAA0000A1Z5" />
          <Input label={t("settings.legalName", "Registered name")} value={legalName} onChange={(e) => setLegalName(e.target.value)} />
          <Textarea label={t("settings.billingAddr", "Billing address")} rows={2} value={billingAddress} onChange={(e) => setBillingAddress(e.target.value)} />
          <Button
            variant="secondary"
            loading={busy}
            onClick={() =>
              save(
                { gstin, legal_name: legalName, billing_address: billingAddress },
                t("settings.savedBilling", "Billing details saved.")
              )
            }
          >
            {t("common.save", "Save")}
          </Button>
        </Card>

        {/* Autopilot */}
        <Card className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.goal", "Your goal")}
          </h2>
          <p className="text-sm text-ink-muted">
            {t("settings.goalDesc", "The most you'll pay for one good lead. Saathi optimises to beat this.")}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {[10000, 20000, 40000, 80000].map((g) => {
              const on = (s.target_cpql_paise || 20000) === g;
              return (
                <button
                  key={g}
                  onClick={() => save({ target_cpql_paise: g }, t("settings.savedGoal", "Goal updated."))}
                  className={`tap font-semibold ${
                    on ? "bg-brand text-white shadow-brand" : "border border-slate-200 bg-white"
                  }`}
                >
                  ≤ ₹{g / 100}/lead
                </button>
              );
            })}
          </div>
        </Card>

        <Card className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.autopilot", "Autopilot")}
          </h2>
          <div className="space-y-2">
            {AUTOPILOT.map((a) => {
              const on = a.value === "ASSISTED"
                ? s.autopilot_level === "ASSISTED" || s.autopilot_level === "FULL"
                : s.autopilot_level === a.value;
              return (
                <button
                  key={a.value}
                  onClick={() =>
                    save({ autopilot_level: a.value }, t("settings.savedAutopilot", "Autopilot updated."))
                  }
                  className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition ${
                    on ? "border-brand bg-brand-50" : "border-slate-200 bg-white"
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                      on ? "border-brand bg-brand text-white" : "border-slate-300"
                    }`}
                  >
                    {on && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                  </span>
                  <span>
                    <span className="block font-semibold">{a.en}</span>
                    <span className="block text-sm text-ink-muted">{a.desc}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </Card>

        {/* Language */}
        <Card className="space-y-2">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-muted">
            {t("settings.language", "Language")}
          </h2>
          <button
            onClick={() => setLangOpen(true)}
            className="flex w-full items-center justify-between rounded-xl border border-slate-200 p-3"
          >
            <span className="font-medium">
              {LANGUAGES.find((l) => l.code === locale)?.label || "English"}
            </span>
            <Icon name="chevronRight" className="text-ink-faint" />
          </button>
        </Card>

        {/* Account actions */}
        <Card className="divide-y divide-slate-100">
          <a
            href="https://wa.me/?text=Hi%20Salmor%20support"
            className="flex items-center gap-3 py-3 text-ink-soft"
          >
            <Icon name="whatsapp" className="text-brand" />
            {t("settings.help", "Help & support")}
          </a>
          <button
            onClick={async () => {
              try {
                await api.logout();
              } catch {
                /* revoke best-effort */
              }
              clearSession();
              router.replace("/login");
            }}
            className="flex w-full items-center gap-3 py-3 text-hot"
          >
            <Icon name="logout" />
            {t("settings.logout", "Log out")}
          </button>
        </Card>

        {/* Data & privacy (DPDP) */}
        <Card className="divide-y divide-slate-100">
          <button
            onClick={async () => {
              try {
                const data = await api.exportMyData();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "salmor-my-data.json";
                a.click();
                URL.revokeObjectURL(url);
              } catch (e: any) {
                toast.show(e.userMessage || t("common.somethingWrong", "Could not export."), "error");
              }
            }}
            className="flex w-full items-center gap-3 py-3 text-ink-soft"
          >
            <Icon name="shield" className="text-brand" />
            {t("settings.exportData", "Download my data")}
          </button>
          <button
            onClick={() => setDeleteOpen(true)}
            className="flex w-full items-center gap-3 py-3 text-hot"
          >
            <Icon name="x" />
            {t("settings.deleteAccount", "Delete my account")}
          </button>
        </Card>
      </div>

      {/* Language picker sheet */}
      <Sheet open={langOpen} onClose={() => setLangOpen(false)} title={t("settings.language", "Language")}>
        <div className="grid grid-cols-2 gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                setLocale(l.code);
                if (acc) save({ default_language: l.code }, t("settings.savedLanguage", "Language updated."));
                setLangOpen(false);
              }}
              className={`rounded-xl border p-3 text-left ${
                locale === l.code ? "border-brand bg-brand-50" : "border-slate-200"
              }`}
            >
              <span className="block font-semibold">{l.label}</span>
              <span className="block text-xs text-ink-faint">{l.english}</span>
            </button>
          ))}
        </div>
      </Sheet>

      <ConfirmDialog
        open={deleteOpen}
        title={t("settings.deleteTitle", "Delete your account?")}
        body={t("settings.deleteBody", "This pauses your ads and removes your data. This can't be undone.")}
        confirmLabel={t("settings.deleteConfirm", "Delete account")}
        tone="danger"
        onConfirm={async () => {
          try {
            await api.deleteMyAccount();
            clearSession();
            router.replace("/login");
          } catch (e: any) {
            toast.show(e.userMessage || t("common.somethingWrong", "Could not delete."), "error");
          }
        }}
        onClose={() => setDeleteOpen(false)}
      />

      <BottomNav active="/settings" />
    </main>
  );
}
