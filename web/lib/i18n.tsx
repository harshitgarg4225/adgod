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
    "dashboard.pauseConfirmTitle": "सभी ऐड्स रोकें?",
    "dashboard.pauseConfirmBody": "Saathi तुरंत खर्च करना बंद कर देगा। आप कभी भी फिर चालू कर सकते हैं — कोई पैसा नहीं जाता।",
    "dashboard.pausedToast": "ऐड्स रोक दिए गए। कंट्रोल आपके पास है।",
    "dashboard.resumedToast": "ऐड्स फिर चालू। Saathi फिर से ग्राहक ढूँढ रहा है।",
    "dashboard.owner": "मालिक",
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
    "dashboard.connectCtaTitle": "बस एक कदम बाकी: ग्राहक आप तक कैसे पहुँचें?",
    "dashboard.connectCtaHint": "WhatsApp या फ़ोन कॉल — आप चुनें",
    "dashboard.preparing": "Saathi आपके ऐड्स तैयार कर रहा है — रिव्यू के लिए यहीं दिखेंगे। अभी आपको कुछ नहीं करना है।",
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
    "ob.step.goal": "लक्ष्य",
    "ob.q.goal": "एक अच्छा ग्राहक आपके लिए कितने का है?",
    "ob.encourage.goal": "Saathi आपकी प्रति-लीड लागत इससे कम रखेगा — सस्ते, बेहतर ग्राहक ढूँढते हुए।",
    "ob.perLead": "≤ ₹{n}/लीड",
    "settings.goal": "आपका लक्ष्य",
    "settings.goalDesc": "एक अच्छे ग्राहक के लिए आप ज़्यादा से ज़्यादा कितना देंगे। Saathi इससे कम पर लाने की कोशिश करेगा।",
    "settings.savedGoal": "लक्ष्य बदल गया।",
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
    "billing.gstTrial": "+ 18% GST · 7 दिन फ्री ट्रायल · कभी भी रद्द करें",
    "billing.securedRazorpay": "Razorpay द्वारा सुरक्षित • UPI ऑटोपे",
    // ── day-1 screen coverage (connect / brief / leads / reports / settings / bookings)
    "bookings.cancel": "बुकिंग रद्द करें",
    "bookings.done": "पूरा हुआ",
    "bookings.emptyHint": "जब आप किसी लीड के साथ मीटिंग तय करेंगे, वह यहाँ दिखेगी।",
    "bookings.emptyTitle": "अभी कोई बुकिंग नहीं",
    "bookings.noTime": "कोई समय तय नहीं",
    "bookings.title": "बुकिंग्स",
    "bookings.updated": "बुकिंग अपडेट हो गई",
    "brief.angles": "Saathi जो ऐड आइडियाज़ आज़माएगा",
    "brief.audience": "हम किसे टारगेट करेंगे",
    "brief.cta": "सही है — मेरे ऐड्स बनाएँ",
    "brief.intro": "मैंने आपका बिज़नेस समझा। यह रही मेरी योजना — बाद में कुछ भी बदल सकते हैं।",
    "brief.loading": "Saathi आपका बिज़नेस समझ रहा है…",
    "brief.offer": "आपकी पेशकश",
    "brief.on": "चालू",
    "brief.paused": "बंद",
    "brief.saved": "अपडेट हो गया। Saathi इसे इस्तेमाल करेगा।",
    "brief.title": "Saathi ने आपके बिज़नेस को ऐसे समझा",
    "brief.usp": "लोग आपको क्यों चुनते हैं",
    "brief.writing": "आपके ऐड्स लिख रहा है…",
    "common.edit": "बदलें",
    "connect.adAccount": "Meta ऐड अकाउंट",
    "connect.adAccountOptional": "अभी ज़रूरी नहीं — Saathi इसे जोड़ने में मदद करता है।",
    "connect.adId": "ऐड अकाउंट ID",
    "connect.aiWa": "Saathi का AI असिस्टेंट",
    "connect.aiWaSub": "24×7 लीड्स को अपने-आप परखता है। WhatsApp API नंबर चाहिए — बाद में चालू करें।",
    "connect.apiHint": "यह आपका WhatsApp प्रोवाइडर देता है।",
    "connect.apiId": "WhatsApp API फ़ोन नंबर ID",
    "connect.building": "Saathi आपके ऐड्स बना रहा है…",
    "connect.cta": "कनेक्ट करें और मेरे ऐड्स बनाएँ",
    "connect.manualHint": "कनेक्ट करने के लिए नीचे अपनी Meta डिटेल भरें।",
    "connect.ownWa": "मेरा अपना WhatsApp (सबसे तेज़)",
    "connect.ownWaSub": "ऐड आपके मौजूदा नंबर पर चैट खोलता है। कोई सेटअप नहीं, इसी हफ़्ते लाइव।",
    "connect.pageId": "Facebook पेज ID",
    "connect.title": "लाइव होने के लिए कनेक्ट करें",
    "connect.where": "लीड्स कहाँ आएँ?",
    "connect.whereSub": "सबसे आसान विकल्प चुनें — कभी भी बदल सकते हैं।",
    "connect.withFacebook": "Facebook से कनेक्ट करें",
    "connect.yourWa": "आपका WhatsApp नंबर",
    "leads.bookAppt": "अपॉइंटमेंट बुक करें",
    "leads.bookHint": "इस लीड से मिलने या कॉल का समय चुनें। यह आपकी बुकिंग्स में चली जाएगी।",
    "leads.booked": "अपॉइंटमेंट बुक हो गई! 🗓️",
    "leads.budget": "बजट",
    "leads.call": "कॉल करें",
    "leads.confirmBooking": "बुकिंग पक्की करें",
    "leads.conversation": "बातचीत",
    "leads.lead": "लीड",
    "leads.location": "जगह",
    "leads.markedFollowup": "Saathi फ़ॉलो-अप करेगा।",
    "leads.markedLost": "खोया हुआ दर्ज किया।",
    "leads.markedWon": "जीत के रूप में दर्ज! 🎉",
    "leads.newEnquiry": "नई पूछताछ",
    "leads.noMessages": "अभी कोई मैसेज नहीं",
    "leads.noMessagesHint": "लीड के जवाब देते ही चैट यहाँ दिखेगी।",
    "leads.rebook": "अपॉइंटमेंट दोबारा तय करें",
    "leads.sent": "WhatsApp पर भेज दिया",
    "leads.slot": "कब",
    "leads.stBooked": "बुक हो गया",
    "leads.stCold": "फ़िट नहीं",
    "leads.stEngaged": "बातचीत जारी",
    "leads.stHandoff": "आपके पास",
    "leads.stQualifying": "परखा जा रहा है",
    "leads.stSilent": "चुप हो गया",
    "leads.timeline": "टाइमलाइन",
    "leads.wants": "क्या चाहिए",
    "leads.wonCelebrate": "सेल जीती! 🎉 शाबाश!",
    "reports.costPerLead": "प्रति लीड लागत",
    "reports.leads": "लीड्स",
    "reports.rBudgetCap": "आपके रोज़ के बजट ने रोका",
    "reports.rCooldown": "आज पहले ही नया ऐड बना दिया",
    "reports.rCpl": "प्रति लीड लागत बहुत ज़्यादा — इसे रोका",
    "reports.rEfficient": "अच्छी प्रति लीड लागत — ज़्यादा बजट दिया",
    "reports.rEmergency": "खर्च सुरक्षा-सीमा तक पहुँचा — सब कुछ रोका",
    "reports.rFatigue": "लोगों ने बहुत बार देखा — नया ऐड बनाया",
    "reports.rPromoted": "टेस्ट ऐड जीता — उसे आगे बढ़ाया",
    "reports.rRealloc": "बजट सबसे अच्छे ऐड पर भेजा",
    "reports.rRejected": "Meta ने एक ऐड नकारा — नया बनाया",
    "reports.rRestart": "आपका सबसे अच्छा ऐड ग्रुप दोबारा चालू किया",
    "reports.rStable": "स्थिर चल रहा",
    "reports.rWinner": "अच्छा चल रहा — ज़्यादा बजट दिया",
    "reports.rZero": "खर्च के बावजूद कोई लीड नहीं — इसे रोका",
    "reports.spend": "खर्च",
    "reports.spendByAd": "ऐड सेट के हिसाब से खर्च (₹)",
    "reports.stillLearning": "अभी कोई बदलाव नहीं — Saathi आपकी लीड्स समझ रहा है।",
    "reports.whatSaathiDid": "Saathi ने क्या किया",
    "settings.billingAddr": "बिलिंग पता",
    "settings.billingDetails": "बिलिंग डिटेल (GST इनवॉइस के लिए)",
    "settings.businessName": "बिज़नेस का नाम",
    "settings.city": "शहर / सेवा क्षेत्र",
    "settings.deleteAccount": "मेरा अकाउंट डिलीट करें",
    "settings.deleteBody": "इससे आपके ऐड्स रुक जाएँगे और डेटा हट जाएगा। यह वापस नहीं होगा।",
    "settings.deleteConfirm": "अकाउंट डिलीट करें",
    "settings.deleteTitle": "अपना अकाउंट डिलीट करें?",
    "settings.exportData": "मेरा डेटा डाउनलोड करें",
    "settings.help": "मदद और सहायता",
    "settings.legalName": "रजिस्टर्ड नाम",
    "settings.logout": "लॉग आउट",
    "settings.offer": "आप क्या देते हैं",
    "settings.perDay": "प्रति दिन",
    "settings.savedAutopilot": "ऑटोपायलट अपडेट हो गया।",
    "settings.savedBilling": "बिलिंग डिटेल सेव हो गई।",
    "settings.savedBusiness": "बिज़नेस डिटेल सेव हो गई।",
    "settings.savedLanguage": "भाषा अपडेट हो गई।",
    "settings.thisMonth": "इस महीने खर्च",
    "settings.updateBudget": "बजट अपडेट करें",
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
