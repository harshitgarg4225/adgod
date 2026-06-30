"use client";

/**
 * Lightweight, dependency-free i18n.
 *
 * Call sites pass the English copy inline as the fallback — `t("key", "English")` — so
 * screens stay readable and we only maintain *override* catalogs for other languages.
 * A missing key (or language) gracefully falls back to the English default, which means
 * partial translations never break the UI. The active locale is persisted and also
 * reflected onto <html lang> for correct screen-reader pronunciation and Devanagari font
 * selection.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Locale = "en" | "hi" | "ta" | "te" | "mr" | "gu" | "kn" | "bn";

export const LANGUAGES: { code: Locale; label: string; english: string }[] = [
  { code: "hi", label: "हिन्दी", english: "Hindi" },
  { code: "en", label: "English", english: "English" },
  { code: "ta", label: "தமிழ்", english: "Tamil" },
  { code: "mr", label: "मराठी", english: "Marathi" },
  { code: "te", label: "తెలుగు", english: "Telugu" },
  { code: "gu", label: "ગુજરાતી", english: "Gujarati" },
  { code: "kn", label: "ಕನ್ನಡ", english: "Kannada" },
  { code: "bn", label: "বাংলা", english: "Bengali" },
];

// Override catalogs. English is supplied inline at call sites, so only non-English needs
// entries. Hindi is the priority (Hindi-first persona); others can be filled over time.
const CATALOG: Partial<Record<Locale, Record<string, string>>> = {
  hi: {
    "common.continue": "आगे बढ़ें",
    "common.back": "वापस",
    "common.retry": "फिर कोशिश करें",
    "common.save": "सेव करें",
    "common.saving": "सेव हो रहा है…",
    "common.cancel": "रद्द करें",
    "common.loading": "लोड हो रहा है…",
    "common.somethingWrong": "कुछ गड़बड़ हुई। थोड़ी देर में फिर कोशिश करें।",
    "common.offline": "आप ऑफ़लाइन हैं — इंटरनेट जुड़ते ही हम फिर कोशिश करेंगे।",
    "nav.home": "होम",
    "nav.leads": "लीड्स",
    "nav.reports": "रिपोर्ट",
    "nav.billing": "बिलिंग",
    "nav.settings": "सेटिंग्स",
    "login.tagline": "आपके ऐड्स और लीड्स का साथी",
    "login.mobile": "मोबाइल नंबर",
    "login.sendOtp": "OTP भेजें",
    "login.sending": "भेज रहे हैं…",
    "login.enterOtp": "OTP डालें",
    "login.verify": "वेरिफाई करें और आगे बढ़ें",
    "login.verifying": "वेरिफाई हो रहा है…",
    "login.changeNumber": "नंबर बदलें",
    "login.trust": "Meta पार्टनर • Razorpay से सुरक्षित भुगतान",
    "dashboard.greeting": "नमस्ते",
    "dashboard.saathiWatching": "Saathi आपके ऐड्स पर 24×7 नज़र रख रहा है",
    "dashboard.spentToday": "आज का खर्च",
    "dashboard.leadsToday": "आज की लीड्स",
    "dashboard.costPerLead": "प्रति लीड लागत",
    "dashboard.pauseAds": "सभी ऐड्स रोकें",
    "dashboard.resumeAds": "ऐड्स फिर चालू करें",
    "dashboard.noLeads": "अभी कोई लीड नहीं — आपके ऐड्स चालू हैं, पहली लीड जल्द आएगी।",
    "leads.hot": "हॉट",
    "leads.won": "जीता",
    "leads.lost": "खोया",
    "leads.followup": "फॉलो-अप",
    "settings.title": "सेटिंग्स",
    "settings.business": "बिज़नेस की जानकारी",
    "settings.budget": "रोज़ का बजट",
    "settings.language": "भाषा",
    "settings.autopilot": "ऑटोपायलट",
    "billing.choosePlan": "प्लान चुनें",
    "billing.securedRazorpay": "Razorpay द्वारा सुरक्षित • UPI ऑटोपे",
  },
};

type Ctx = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, fallback: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<Ctx | null>(null);
const STORAGE_KEY = "salmor_locale";

function interpolate(s: string, vars?: Record<string, string | number>): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = (typeof window !== "undefined" &&
      window.localStorage.getItem(STORAGE_KEY)) as Locale | null;
    if (stored) setLocaleState(stored);
  }, []);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = (l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  };

  const t = (key: string, fallback: string, vars?: Record<string, string | number>) => {
    const hit = CATALOG[locale]?.[key];
    return interpolate(hit ?? fallback, vars);
  };

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>
  );
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Safe no-op fallback if a component renders outside the provider (e.g. tests).
    return { locale: "en", setLocale: () => {}, t: (_k, f, v) => interpolate(f, v) };
  }
  return ctx;
}

/** Convenience hook returning just the translate function. */
export function useT() {
  return useI18n().t;
}
