"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { Button, Card, Icon, Input, TopBar, useToast } from "@/components/ui";

export default function Connect() {
  const router = useRouter();
  const t = useT();
  const toast = useToast();
  const [mode, setMode] = useState<"APP_DESTINATION" | "CLOUD_API" | "CALL">("APP_DESTINATION");
  const [phone, setPhone] = useState("");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [adAccount, setAdAccount] = useState("");
  const [pageId, setPageId] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);

  async function connect() {
    setBusy(true);
    try {
      await api.connectWhatsApp(
        mode === "CLOUD_API" ? { mode, phone_number_id: phoneNumberId } : { mode, phone }
      );
      if (adAccount && pageId) {
        await api.connectMeta({ meta_business_id: adAccount, ad_account_id: adAccount, page_id: pageId });
      }
      const account = getUser()?.account_id;
      if (account) await api.runResearch(account);
      router.replace("/onboarding/brief");
    } catch (e: any) {
      toast.show(e.userMessage || t("common.somethingWrong", "Could not connect."), "error");
      setBusy(false);
    }
  }

  const canContinue = mode === "CLOUD_API"
    ? phoneNumberId.trim().length > 0
    : phone.trim().length >= 6;

  return (
    <main className="min-h-[100dvh] pb-28">
      <TopBar title={t("connect.title", "Connect to go live")} back="/onboarding" />
      <section className="space-y-5 p-4">
        <div>
          <h2 className="mb-1 text-lg font-bold">{t("connect.where", "Where should leads go?")}</h2>
          <p className="mb-3 text-sm text-ink-muted">
            {t("connect.whereSub", "Pick the simplest option — you can switch anytime.")}
          </p>
          <div className="grid gap-2">
            <Choice
              active={mode === "APP_DESTINATION"}
              onClick={() => setMode("APP_DESTINATION")}
              icon="whatsapp"
              title={t("connect.ownWa", "My own WhatsApp (fastest)")}
              sub={t("connect.ownWaSub", "Ads open a chat on your existing number. No setup, live this week.")}
            />
            <Choice
              active={mode === "CALL"}
              onClick={() => setMode("CALL")}
              icon="phone"
              title={t("connect.calls", "Phone calls")}
              sub={t("connect.callsSub", "Customers tap the ad and call you directly.")}
            />
            <Choice
              active={mode === "CLOUD_API"}
              onClick={() => setMode("CLOUD_API")}
              icon="sparkle"
              title={t("connect.aiWa", "Saathi's AI assistant")}
              sub={t("connect.aiWaSub", "Auto-qualifies leads 24×7. Needs a WhatsApp API number — turn on later.")}
            />
          </div>
        </div>

        {mode !== "CLOUD_API" ? (
          <Input
            label={mode === "CALL"
              ? t("connect.yourPhone", "Your phone number (for calls)")
              : t("connect.yourWa", "Your WhatsApp number")}
            inputMode="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+91…"
          />
        ) : (
          <Input
            label={t("connect.apiId", "WhatsApp API phone number ID")}
            value={phoneNumberId}
            onChange={(e) => setPhoneNumberId(e.target.value)}
            placeholder="phone_number_id"
            hint={t("connect.apiHint", "Your WhatsApp provider gives you this.")}
          />
        )}

        {/* Meta connect — one-tap OAuth (Embedded Signup); manual is the dev fallback */}
        <Button
          fullWidth
          variant="secondary"
          leftIcon="shield"
          onClick={async () => {
            try {
              const r = await api.metaEmbeddedStart();
              if (r.configured && r.url) window.location.href = r.url;
              else {
                setShowAdvanced(true);
                toast.show(t("connect.manualHint", "Enter your Meta details below to connect."), "info");
              }
            } catch (e: any) {
              toast.show(e.userMessage || t("common.somethingWrong", "Could not start."), "error");
            }
          }}
        >
          {t("connect.withFacebook", "Connect with Facebook")}
        </Button>

        {/* Advanced: Meta ad account — optional, Saathi helps in production */}
        <Card className="!p-0">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex w-full items-center justify-between p-4"
          >
            <span className="text-left">
              <span className="block font-semibold">{t("connect.adAccount", "Meta ad account")}</span>
              <span className="block text-sm text-ink-muted">
                {t("connect.adAccountOptional", "Optional now — Saathi helps connect this for you.")}
              </span>
            </span>
            <Icon name={showAdvanced ? "chevronLeft" : "chevronRight"} className="text-ink-faint" />
          </button>
          {showAdvanced && (
            <div className="space-y-2 px-4 pb-4">
              <Input value={adAccount} onChange={(e) => setAdAccount(e.target.value)} placeholder={t("connect.adId", "Ad account ID")} />
              <Input value={pageId} onChange={(e) => setPageId(e.target.value)} placeholder={t("connect.pageId", "Facebook Page ID")} />
            </div>
          )}
        </Card>
      </section>

      <div className="cta-dock">
        <Button fullWidth size="lg" leftIcon="sparkle" loading={busy} disabled={!canContinue} onClick={connect}>
          {busy ? t("connect.building", "Saathi is building your ads…") : t("connect.cta", "Connect & build my ads")}
        </Button>
      </div>
    </main>
  );
}

function Choice({
  active,
  onClick,
  title,
  sub,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  sub: string;
  icon: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-start gap-3 rounded-2xl border p-3.5 text-left transition ${
        active ? "border-brand bg-brand-50 shadow-card" : "border-slate-200 bg-white"
      }`}
    >
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${
          active ? "bg-brand text-white" : "bg-slate-100 text-ink-muted"
        }`}
      >
        <Icon name={icon} />
      </span>
      <span>
        <span className="block font-semibold">{title}</span>
        <span className="block text-sm text-ink-muted">{sub}</span>
      </span>
    </button>
  );
}
