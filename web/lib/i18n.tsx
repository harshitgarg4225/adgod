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
    "login.invalidPhone": "सही 10 अंकों का मोबाइल नंबर डालें।",
    "login.sendFailed": "कोड नहीं भेज पाए। फिर कोशिश करें।",
    "login.invalidCode": "ग़लत कोड — SMS देखकर दोबारा डालें।",
    "login.haveCode": "मेरे पास पहले से कोड है",
    "login.consent": "आगे बढ़ने पर आप हमारी शर्तें और प्राइवेसी पॉलिसी मानते हैं।",
    "login.trust": "OTP से सुरक्षित लॉगिन • आपका डेटा आपका ही रहेगा",
    "dashboard.greeting": "नमस्ते",
    "dashboard.saathiWatching": "Saathi आपके ऐड्स पर 24×7 नज़र रख रहा है",
    "dashboard.spentToday": "आज का खर्च",
    "dashboard.leadsToday": "आज की लीड्स",
    "dashboard.costPerLead": "प्रति लीड लागत",
    "dashboard.pauseAds": "सभी ऐड्स रोकें",
    "dashboard.resumeAds": "ऐड्स फिर चालू करें",
    "dashboard.noLeads": "अभी कोई लीड नहीं — आपके ऐड्स चालू हैं, पहली लीड जल्द आएगी।",
    "dashboard.noLeadsTitle": "अभी कोई लीड नहीं",
    "dashboard.noLeadsPrelaunch": "ऐड्स चालू होते ही लीड्स यहाँ दिखेंगी।",
    "dashboard.leadsUnavailable": "लीड्स लोड नहीं हुईं — फिर कोशिश करें।",
    "dashboard.recentLeads": "हाल की लीड्स",
    "dashboard.spend7d": "पिछले 7 दिन",
    "dashboard.dailyCap": "रोज़ की सीमा",
    "dashboard.noSpendYet": "अभी कोई खर्च नहीं",
    "dashboard.adsPaused": "ऐड्स रुके हुए हैं",
    "dashboard.adsRunning": "ऐड्स चल रहे हैं",
    "dashboard.youControl": "खर्च पर कंट्रोल हमेशा आपका है।",
    "dashboard.approveCtaTitle": "आपके ऐड्स रिव्यू के लिए तैयार हैं",
    "dashboard.approveCtaHint": "टैप करें — अप्रूव करें और लाइव जाएँ",
    "common.seeAll": "सब देखें",
    "common.tryAgain": "फिर कोशिश करें",
    "leads.hot": "हॉट लीड",
    "leads.warm": "वॉर्म",
    "leads.cold": "कोल्ड",
    "leads.spam": "स्पैम",
    "leads.won": "जीता",
    "leads.lost": "खोया",
    "leads.followup": "फॉलो-अप",
    "leads.search": "नाम या नंबर खोजें",
    "leads.filterAll": "सभी",
    "leads.filterHot": "हॉट",
    "leads.filterWarm": "वॉर्म",
    "leads.filterWon": "जीते",
    "leads.add": "लीड जोड़ें",
    "leads.addPhone": "WhatsApp नंबर",
    "leads.addName": "नाम",
    "leads.addNote": "उन्हें क्या चाहिए? (ऑप्शनल)",
    "leads.addSave": "लीड सेव करें",
    "leads.added": "लीड जुड़ गई",
    "leads.export": "CSV डाउनलोड करें",
    "leads.emptyTitle": "अभी यहाँ कोई लीड नहीं",
    "leads.emptyHint": "ऐड्स से आई पूछताछ आपके WhatsApp पर खुलती है — उन्हें + से यहाँ दर्ज करें ताकि Saathi नतीजे दिखा सके।",
    "leads.reply": "WhatsApp पर जवाब दें…",
    "leads.send": "भेजें",
    "creatives.title": "आपके ऐड्स तैयार हैं",
    "creatives.loading": "Saathi आपके ऐड्स बना रहा है…",
    "creatives.intro": "Saathi ने ये आपके लिए लिखे हैं। देख लें — बाद में कुछ भी बदल सकते हैं।",
    "creatives.policyOk": "पॉलिसी OK",
    "creatives.needsFix": "सुधार चाहिए",
    "creatives.keep": "यह रखें",
    "creatives.reject": "हटाएँ",
    "creatives.keepOne": "लॉन्च के लिए कम से कम एक ऐड रखें।",
    "creatives.fixFirst": "लाइव जाने से पहले एक ऐड में सुधार चाहिए।",
    "creatives.launch": "मेरे ऐड्स लॉन्च करें",
    "creatives.launching": "लॉन्च हो रहा है…",
    "creatives.launched": "आपके ऐड्स लाइव हैं! Saathi 24×7 नज़र रखेगा 🎉",
    "creatives.emptyTitle": "Saathi अभी डिज़ाइन कर रहा है",
    "creatives.emptyHint": "आपके ऐड्स बन रहे हैं — एक मिनट में देखें।",
    "ob.title": "चलिए आपके ऐड्स सेट करें",
    "ob.back": "पीछे",
    "reports.preparing": "आपकी रिपोर्ट बन रही है…",
    "notifications.title": "सूचनाएँ",
    "notifications.emptyTitle": "सब देख लिया",
    "notifications.emptyHint": "हॉट लीड्स और अपडेट्स की खबर Saathi यहाँ देगा।",
    "billing.manualNote": "बिलिंग आपके Salmor मैनेजर के पास है।",
    "billing.contactManager": "अपने मैनेजर से बात करें",
    "billing.day": "दिन",
    "dashboard.seeMyAds": "मेरे ऐड्स देखें",
    "dashboard.change": "बदलें",
    "dashboard.changeBudget": "रोज़ का बजट",
    "dashboard.budgetSafety": "Saathi एक दिन में इससे ज़्यादा कभी खर्च नहीं करेगा।",
    "settings.savedBudget": "बजट बदल गया।",
    "ads.title": "मेरे ऐड्स",
    "ads.running": "चल रहा है",
    "ads.inReview": "Meta रिव्यू में",
    "ads.fixing": "ठीक हो रहा है",
    "ads.waCampaign": "WhatsApp ऐड्स",
    "ads.callCampaign": "कॉल ऐड्स",
    "ads.live": "चालू — {n} ऐड ग्रुप चल रहे हैं",
    "ads.paused": "रुका हुआ",
    "ads.someInReview": "{n} Meta रिव्यू में",
    "ads.emptyTitle": "अभी कोई ऐड लाइव नहीं",
    "ads.emptyHint": "ऐड्स लॉन्च होते ही यहाँ दिखेंगे।",
    "connect.calls": "फ़ोन कॉल",
    "connect.callsSub": "ग्राहक ऐड पर टैप करके सीधे आपको कॉल करेंगे।",
    "connect.yourPhone": "आपका फ़ोन नंबर (कॉल के लिए)",
    "creatives.launchQueued": "लॉन्च हो रहा है — लाइव होते ही बताऊँगा।",
    "creatives.alreadyLive": "आपके ऐड्स लाइव हैं — देखें",
    "creatives.metaPending": "Saathi की टीम आपके लिए Facebook जोड़ रही है — आपको कुछ नहीं करना। अप्रूव किए ऐड्स अपने आप लॉन्च होंगे।",
    "creatives.approveOnly": "मेरे ऐड्स अप्रूव करें",
    "creatives.approvedWaiting": "अप्रूव हो गया! Facebook जुड़ते ही ऐड्स लॉन्च होंगे।",
    "brief.researching": "Saathi आपका बिज़नेस समझ रहा है…",
    "leads.stNew": "नई",
    "leads.stHot": "हॉट — अभी कॉल करें",
    "leads.stWarm": "वॉर्म",
    "leads.srcAds": "आपके ऐड्स से",
    "leads.srcForm": "Facebook फ़ॉर्म",
    "leads.srcManual": "आपने जोड़ा",
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
