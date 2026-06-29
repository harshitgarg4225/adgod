"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, saveSession } from "@/lib/api";

export default function Login() {
  const router = useRouter();
  const [phone, setPhone] = useState("+919876500000");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function sendOtp() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.requestOtp(phone);
      setDevCode(r.dev_code ?? null);
      if (r.dev_code) setCode(r.dev_code);
      setStep("code");
    } catch (e: any) {
      setError(e.userMessage || "Could not send code");
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      const t = await api.verifyOtp(phone, code);
      saveSession(t);
      router.replace("/dashboard");
    } catch (e: any) {
      setError(e.userMessage || "Invalid code");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col justify-center gap-6 px-6">
      <div className="text-center">
        <div className="text-4xl">🚀</div>
        <h1 className="mt-2 text-2xl font-extrabold text-brand">LeadPilot</h1>
        <p className="text-sm text-slate-500">Qualified WhatsApp leads, on autopilot.</p>
      </div>

      {step === "phone" ? (
        <div className="flex flex-col gap-3">
          <label className="text-sm font-medium">Mobile number</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="tel"
            className="tap border text-lg"
            placeholder="+91…"
          />
          <button onClick={sendOtp} disabled={busy} className="tap bg-brand text-white font-semibold disabled:opacity-50">
            {busy ? "Sending…" : "Send OTP"}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <label className="text-sm font-medium">Enter OTP</label>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode="numeric"
            className="tap border text-center text-2xl tracking-[0.5em]"
            placeholder="000000"
          />
          {devCode && (
            <p className="text-center text-xs text-slate-400">Dev code: {devCode}</p>
          )}
          <button onClick={verify} disabled={busy} className="tap bg-brand text-white font-semibold disabled:opacity-50">
            {busy ? "Verifying…" : "Verify & continue"}
          </button>
          <button onClick={() => setStep("phone")} className="text-sm text-slate-400">
            Change number
          </button>
        </div>
      )}

      {error && <p className="text-center text-sm text-hot">{error}</p>}
    </main>
  );
}
