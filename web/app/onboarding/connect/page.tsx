"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import { TopBar } from "@/components/ui";

export default function Connect() {
  const router = useRouter();
  const [mode, setMode] = useState<"APP_DESTINATION" | "CLOUD_API">("APP_DESTINATION");
  const [phone, setPhone] = useState("");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [adAccount, setAdAccount] = useState("");
  const [pageId, setPageId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      await api.connectWhatsApp(
        mode === "APP_DESTINATION"
          ? { mode, phone }
          : { mode, phone_number_id: phoneNumberId }
      );
      if (adAccount && pageId) {
        await api.connectMeta({
          meta_business_id: adAccount,
          ad_account_id: adAccount,
          page_id: pageId,
        });
      }
      const account = getUser()?.account_id;
      if (account) await api.runResearch(account);
      router.replace("/onboarding/brief");
    } catch (e: any) {
      setError(e.userMessage || "Could not connect");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="pb-28">
      <TopBar title="Connect to go live" back="/onboarding" />
      <section className="space-y-5 p-4">
        <div>
          <h2 className="mb-2 text-lg font-bold">Where should leads go?</h2>
          <div className="grid grid-cols-1 gap-2">
            <Choice
              active={mode === "APP_DESTINATION"}
              onClick={() => setMode("APP_DESTINATION")}
              title="My own WhatsApp (fastest — live this week)"
              sub="Ads open a chat on your existing WhatsApp number. No setup, no waiting."
            />
            <Choice
              active={mode === "CLOUD_API"}
              onClick={() => setMode("CLOUD_API")}
              title="Saathi's AI assistant (auto-qualifies leads)"
              sub="Needs a WhatsApp API number (via a provider). Turn on anytime later."
            />
          </div>
        </div>

        {mode === "APP_DESTINATION" ? (
          <Field label="Your WhatsApp number">
            <input className="tap w-full border text-lg" inputMode="tel" value={phone}
              onChange={(e) => setPhone(e.target.value)} placeholder="+91…" />
          </Field>
        ) : (
          <Field label="WhatsApp API phone number ID">
            <input className="tap w-full border" value={phoneNumberId}
              onChange={(e) => setPhoneNumberId(e.target.value)} placeholder="phone_number_id" />
          </Field>
        )}

        <div>
          <h2 className="mb-2 text-lg font-bold">Meta ad account</h2>
          <p className="mb-2 text-xs text-slate-500">
            Connect the account that will run your ads. (Embedded Signup wires this
            automatically in production.)
          </p>
          <div className="space-y-2">
            <input className="tap w-full border" value={adAccount}
              onChange={(e) => setAdAccount(e.target.value)} placeholder="Ad account ID" />
            <input className="tap w-full border" value={pageId}
              onChange={(e) => setPageId(e.target.value)} placeholder="Facebook Page ID" />
          </div>
        </div>

        {error && <p className="text-center text-sm text-hot">{error}</p>}
      </section>

      <div className="fixed inset-x-0 bottom-0 mx-auto max-w-md border-t bg-white p-3">
        <button onClick={connect} disabled={busy}
          className="tap w-full bg-brand font-semibold text-white disabled:opacity-50">
          {busy ? "Saathi is building your ads…" : "Connect & build my ads →"}
        </button>
      </div>
    </main>
  );
}

function Choice({ active, onClick, title, sub }: {
  active: boolean; onClick: () => void; title: string; sub: string;
}) {
  return (
    <button onClick={onClick}
      className={`rounded-2xl border p-3 text-left ${active ? "border-brand bg-brand-light" : ""}`}>
      <p className="font-semibold">{title}</p>
      <p className="text-sm text-slate-500">{sub}</p>
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-slate-600">{label}</h3>
      {children}
    </div>
  );
}
