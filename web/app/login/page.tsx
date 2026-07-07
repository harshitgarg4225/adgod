"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, saveSession } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Button, Icon, Input, SaathiAvatar } from "@/components/ui";

const PHONE_RE = /^\+?[6-9]\d{9}$/;

export default function Login() {
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const normalized = phone.startsWith("+") ? phone : `+91${phone.replace(/^91/, "")}`;
  const phoneValid = PHONE_RE.test(phone.replace(/^\+91/, "").replace(/\s/g, ""));

  async function sendOtp() {
    if (!phoneValid) {
      setError(t("login.invalidPhone", "Enter a valid 10-digit mobile number."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await api.requestOtp(normalized);
      setDevCode(r.dev_code ?? null);
      if (r.dev_code) setCode(r.dev_code);
      setStep("code");
    } catch (e: any) {
      setError(e.userMessage || t("login.sendFailed", "Could not send the code. Try again."));
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      const tk = await api.verifyOtp(normalized, code);
      saveSession(tk);
      // Hindi-first: apply the account's stored language immediately (provisioned owners
      // have locale=hi; without this the whole first run renders in English).
      const userLocale = (tk.user as any)?.locale;
      if (userLocale === "hi" || userLocale === "en") setLocale(userLocale);
      // Route by role: an admin/partner has no owner account — /dashboard would bounce
      // them straight back to /login in a loop.
      const role = (tk.user as any)?.role;
      if (role === "ADMIN" || role === "OPS") return router.replace("/admin");
      if (role === "PARTNER") return router.replace("/partner");
      // New accounts (no business set up yet) land in onboarding; everyone else goes home.
      let dest = "/dashboard";
      try {
        const st = await api.onboardingStatus();
        if (st.missing_steps?.includes("business_profile")) dest = "/onboarding";
        // Provisioned owners already have a business profile but still owe one answer —
        // where leads should reach them. Never strand them on the dashboard.
        else if (st.missing_steps?.includes("whatsapp_connection")) dest = "/onboarding/connect";
      } catch {
        /* fall back to dashboard */
      }
      router.replace(dest);
    } catch (e: any) {
      setError(e.userMessage || t("login.invalidCode", "Wrong code — check your SMS and retry."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-[100dvh] flex-col px-6 pb-10 pt-16">
      <div className="flex flex-1 flex-col justify-center gap-8">
        {/* Brand */}
        <div className="flex flex-col items-center text-center">
          <SaathiAvatar size={72} className="animate-pop drop-shadow" />
          <h1 className="mt-4 text-3xl font-bold tracking-tight">Salmor</h1>
          <p className="mt-1 max-w-xs text-ink-muted deva">
            {t("login.tagline", "Your Saathi for ads & WhatsApp leads")}
          </p>
        </div>

        {/* Language — Hindi-first owners must not face an English wall on screen one */}
        <div className="flex justify-center gap-2">
          {([["hi", "हिन्दी"], ["en", "English"]] as const).map(([l, label]) => (
            <button
              key={l}
              onClick={() => setLocale(l)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium ${
                locale === l ? "bg-brand text-white" : "border border-slate-200 text-ink-soft"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Form */}
        {step === "phone" ? (
          <div className="flex flex-col gap-4 animate-slide-up">
            <Input
              label={t("login.mobile", "Mobile number")}
              name="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              inputMode="tel"
              autoComplete="tel"
              placeholder="98765 43210"
              error={error ?? undefined}
              maxLength={14}
            />
            <Button fullWidth size="lg" loading={busy} onClick={sendOtp}>
              {busy ? t("login.sending", "Sending…") : t("login.sendOtp", "Send OTP")}
            </Button>
            <button
              onClick={() => {
                // Operator-minted codes (no SMS): jump straight to code entry — the
                // send step failing must never block a code that already exists.
                if (!phoneValid) {
                  setError(t("login.invalidPhone", "Enter a valid 10-digit mobile number."));
                  return;
                }
                setError(null);
                setStep("code");
              }}
              className="text-sm font-medium text-ink-muted hover:text-ink"
            >
              {t("login.haveCode", "I already have a code")}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-4 animate-slide-up">
            <Input
              label={t("login.enterOtp", "Enter OTP")}
              name="otp"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              maxLength={6}
              className="text-center text-2xl tracking-[0.5em]"
              placeholder="000000"
              error={error ?? undefined}
              hint={devCode ? `Dev code: ${devCode}` : undefined}
            />
            <Button fullWidth size="lg" loading={busy} disabled={code.length < 6} onClick={verify}>
              {busy ? t("login.verifying", "Verifying…") : t("login.verify", "Verify & continue")}
            </Button>
            <button
              onClick={() => {
                setStep("phone");
                setError(null);
              }}
              className="text-sm font-medium text-ink-muted hover:text-ink"
            >
              {t("login.changeNumber", "Change number")}
            </button>
          </div>
        )}
      </div>

      {/* Consent + Trust */}
      <div className="space-y-2 text-center">
        <p className="text-2xs text-ink-faint">
          {t("login.consent", "By continuing you agree to our Terms & Privacy Policy.")}
        </p>
        <div className="flex items-center justify-center gap-2 text-xs text-ink-faint">
          <Icon name="shield" className="h-4 w-4" />
          {t("login.trust", "OTP-secured login • Your data stays yours")}
        </div>
      </div>
    </main>
  );
}
