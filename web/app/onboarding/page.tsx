"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, getUser } from "@/lib/api";
import { TopBar } from "@/components/ui";

const CATEGORIES = [
  "coaching", "clinic", "gym", "salon", "real_estate", "interior",
  "education_consultant", "healthcare", "other",
];
const BUDGETS = [30000, 50000, 100000]; // paise: ₹300 / ₹500 / ₹1,000
const LANGS = [
  { code: "hi", label: "हिन्दी" },
  { code: "en", label: "English" },
  { code: "ta", label: "தமிழ்" },
  { code: "mr", label: "मराठी" },
];

export default function Onboarding() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    business_name: "",
    category: "coaching",
    offer: "",
    city: "",
    radius_km: 10,
    daily_budget_paise: 50000,
    language: "hi",
  });

  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));
  const steps = ["Business", "Offer", "Area", "Budget", "Language"];

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      const account = getUser()?.account_id;
      await api.setBusiness(form);
      if (account) await api.runResearch(account);
      router.replace("/onboarding/brief");
    } catch (e: any) {
      setError(e.userMessage || "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="pb-10">
      <TopBar title="Set up in 5 steps" />
      <div className="px-5 pt-2">
        <div className="mb-4 flex gap-1">
          {steps.map((_, i) => (
            <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-brand" : "bg-slate-200"}`} />
          ))}
        </div>

        {step === 0 && (
          <Field label="What's your business name?">
            <input className="tap w-full border text-lg" value={form.business_name}
              onChange={(e) => set("business_name", e.target.value)} placeholder="e.g. Sharma NEET Classes" />
            <Picker options={CATEGORIES} value={form.category} onChange={(v) => set("category", v)} />
          </Field>
        )}
        {step === 1 && (
          <Field label="What do you sell / your main offer?">
            <textarea className="w-full rounded-xl border p-3 text-lg" rows={4} value={form.offer}
              onChange={(e) => set("offer", e.target.value)}
              placeholder="e.g. NEET coaching with small batches and weekly tests" />
          </Field>
        )}
        {step === 2 && (
          <Field label="Which city, and how far?">
            <input className="tap w-full border text-lg" value={form.city}
              onChange={(e) => set("city", e.target.value)} placeholder="e.g. Indore" />
            <label className="mt-3 block text-sm text-slate-500">Radius: {form.radius_km} km</label>
            <input type="range" min={2} max={50} value={form.radius_km}
              onChange={(e) => set("radius_km", Number(e.target.value))} className="w-full accent-brand" />
          </Field>
        )}
        {step === 3 && (
          <Field label="Daily ad budget">
            <div className="grid grid-cols-3 gap-2">
              {BUDGETS.map((b) => (
                <button key={b} onClick={() => set("daily_budget_paise", b)}
                  className={`tap font-semibold ${form.daily_budget_paise === b ? "bg-brand text-white" : "border"}`}>
                  ₹{b / 100}
                </button>
              ))}
            </div>
          </Field>
        )}
        {step === 4 && (
          <Field label="Preferred language">
            <div className="grid grid-cols-2 gap-2">
              {LANGS.map((l) => (
                <button key={l.code} onClick={() => set("language", l.code)}
                  className={`tap font-semibold ${form.language === l.code ? "bg-brand text-white" : "border"}`}>
                  {l.label}
                </button>
              ))}
            </div>
          </Field>
        )}

        {error && <p className="mt-3 text-center text-sm text-hot">{error}</p>}

        <div className="mt-6 flex gap-2">
          {step > 0 && (
            <button onClick={() => setStep((s) => s - 1)} className="tap flex-1 border font-medium">Back</button>
          )}
          {step < steps.length - 1 ? (
            <button onClick={() => setStep((s) => s + 1)} className="tap flex-1 bg-brand font-semibold text-white">
              Next
            </button>
          ) : (
            <button onClick={finish} disabled={busy} className="tap flex-1 bg-brand font-semibold text-white disabled:opacity-50">
              {busy ? "Saathi is researching…" : "Create my ads →"}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 text-lg font-bold">{label}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Picker({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)}
          className={`rounded-full px-3 py-1.5 text-sm ${value === o ? "bg-brand text-white" : "border"}`}>
          {o.replace(/_/g, " ")}
        </button>
      ))}
    </div>
  );
}
