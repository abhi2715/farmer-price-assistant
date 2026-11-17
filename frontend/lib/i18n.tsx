"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "hi" | "kn";
export const LANGS: { code: Lang; label: string; speech: string }[] = [
  { code: "kn", label: "ಕನ್ನಡ", speech: "kn-IN" },
  { code: "hi", label: "हिन्दी", speech: "hi-IN" },
  { code: "en", label: "English", speech: "en-IN" },
];

type Dict = Record<string, [string, string, string]>; // en, hi, kn
const D: Dict = {
  login: ["Log in", "लॉग इन", "ಲಾಗಿನ್"],
  logout: ["Log out", "लॉग आउट", "ಲಾಗ್ ಔಟ್"],
  phone: ["Mobile number", "मोबाइल नंबर", "ಮೊಬೈಲ್ ಸಂಖ್ಯೆ"],
  send_otp: ["Send OTP", "OTP भेजें", "OTP ಕಳುಹಿಸಿ"],
  otp: ["Enter the 6-digit OTP", "6 अंकों का OTP डालें", "6 ಅಂಕಿಯ OTP ನಮೂದಿಸಿ"],
  verify: ["Verify & continue", "पुष्टि करें", "ಪರಿಶೀಲಿಸಿ"],
  dev_otp: ["Demo OTP: {otp}", "डेमो OTP: {otp}", "ಡೆಮೋ OTP: {otp}"],
  i_am: ["I am a", "मैं हूँ", "ನಾನು"],
  role_farmer: ["Farmer", "किसान", "ರೈತ"],
  role_buyer: ["Buyer", "खरीदार", "ಖರೀದಿದಾರ"],
  your_name: ["Your name (new users)", "आपका नाम (नए उपयोगकर्ता)", "ನಿಮ್ಮ ಹೆಸರು (ಹೊಸ ಬಳಕೆದಾರರು)"],
  demo_accounts: ["Demo accounts", "डेमो खाते", "ಡೆಮೋ ಖಾತೆಗಳು"],
  step_crop: ["What are you selling?", "आप क्या बेच रहे हैं?", "ನೀವು ಏನು ಮಾರುತ್ತಿದ್ದೀರಿ?"],
  step_qty: ["How much?", "कितना?", "ಎಷ್ಟು?"],
  quintal: ["quintal", "क्विंटल", "ಕ್ವಿಂಟಾಲ್"],
  qtl: ["qtl", "क्विं.", "ಕ್ವಿಂ"],
  show_best: ["Show best option", "सबसे अच्छा विकल्प दिखाएँ", "ಉತ್ತಮ ಆಯ್ಕೆ ತೋರಿಸಿ"],
  best_option: ["Best option", "सबसे अच्छा विकल्प", "ಅತ್ಯುತ್ತಮ ಆಯ್ಕೆ"],
  today: ["Today", "आज", "ಇಂದು"],
  in_days: ["In {n} days", "{n} दिन में", "{n} ದಿನಗಳಲ್ಲಿ"],
  you_get: ["You take home", "आपको मिलेंगे", "ನಿಮಗೆ ಸಿಗುವುದು"],
  more_than_nearest: ["₹{n} more than selling today nearby", "आज नज़दीक बेचने से ₹{n} ज़्यादा", "ಇಂದು ಹತ್ತಿರ ಮಾರುವುದಕ್ಕಿಂತ ₹{n} ಹೆಚ್ಚು"],
  why: ["Why this recommendation", "यह सलाह क्यों", "ಈ ಸಲಹೆ ಏಕೆ"],
  why_price: ["Why we expect this price", "हम यह भाव क्यों मान रहे हैं", "ಈ ಬೆಲೆ ನಿರೀಕ್ಷೆಗೆ ಕಾರಣ"],
  price_per_qtl: ["Price / qtl", "भाव / क्विं.", "ಬೆಲೆ / ಕ್ವಿಂ"],
  gross: ["Sale value", "बिक्री मूल्य", "ಮಾರಾಟ ಮೌಲ್ಯ"],
  transport: ["Transport", "ढुलाई", "ಸಾಗಣೆ"],
  fees: ["Mandi fees", "मंडी शुल्क", "ಮಂಡಿ ಶುಲ್ಕ"],
  spoilage: ["Spoilage", "खराबी", "ಹಾಳಾಗುವಿಕೆ"],
  holding: ["Waiting cost", "रुकने का खर्च", "ಕಾಯುವ ವೆಚ್ಚ"],
  net: ["Net profit", "शुद्ध लाभ", "ನಿವ್ವಳ ಲಾಭ"],
  worst_case: ["Bad case", "बुरी स्थिति", "ಕೆಟ್ಟ ಸಂದರ್ಭ"],
  other_options: ["Other mandis", "अन्य मंडियाँ", "ಇತರ ಮಂಡಿಗಳು"],
  find_buyer: ["Find a direct buyer", "सीधा खरीदार खोजें", "ನೇರ ಖರೀದಿದಾರರನ್ನು ಹುಡುಕಿ"],
  listen: ["Listen", "सुनें", "ಕೇಳಿ"],
  speak: ["Speak", "बोलें", "ಮಾತನಾಡಿ"],
  listening: ["Listening…", "सुन रहे हैं…", "ಕೇಳುತ್ತಿದೆ…"],
  voice_hint: ['Say: "Tomato 20 quintal"', 'बोलें: "टमाटर 20 क्विंटल"', 'ಹೇಳಿ: "ಟೊಮೆಟೊ 20 ಕ್ವಿಂಟಾಲ್"'],
  start_over: ["Start over", "फिर से", "ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಿ"],
  nav_sell: ["Sell", "बेचें", "ಮಾರಾಟ"],
  nav_prices: ["Prices", "भाव", "ಬೆಲೆಗಳು"],
  nav_lots: ["My lots", "मेरा माल", "ನನ್ನ ಸರಕು"],
  nav_alerts: ["Alerts", "सूचनाएँ", "ಎಚ್ಚರಿಕೆಗಳು"],
  forecast: ["Price forecast", "भाव का अनुमान", "ಬೆಲೆ ಮುನ್ಸೂಚನೆ"],
  mandi: ["Mandi", "मंडी", "ಮಂಡಿ"],
  crop: ["Crop", "फ़सल", "ಬೆಳೆ"],
  days_n: ["{n} days", "{n} दिन", "{n} ದಿನ"],
  now: ["Now", "अभी", "ಈಗ"],
  range: ["Likely range", "संभावित दायरा", "ಸಂಭಾವ್ಯ ವ್ಯಾಪ್ತಿ"],
  accuracy: ["Typical error ±{n}%", "सामान्य त्रुटि ±{n}%", "ಸಾಮಾನ್ಯ ದೋಷ ±{n}%"],
  grade: ["Grade", "ग्रेड", "ಗ್ರೇಡ್"],
  ask_price: ["Your price / qtl (₹)", "आपका भाव / क्विं. (₹)", "ನಿಮ್ಮ ಬೆಲೆ / ಕ್ವಿಂ (₹)"],
  post_lot: ["Post lot", "माल डालें", "ಸರಕು ಪೋಸ್ಟ್ ಮಾಡಿ"],
  new_lot: ["Sell to a buyer", "खरीदार को बेचें", "ಖರೀದಿದಾರರಿಗೆ ಮಾರಿ"],
  posted_matched: ["Posted! {n} buyer match found.", "माल डाला गया! {n} खरीदार मिला।", "ಪೋಸ್ಟ್ ಆಯಿತು! {n} ಖರೀದಿದಾರ ಸಿಕ್ಕಿದ್ದಾರೆ."],
  posted_waiting: ["Posted! We'll alert you when a buyer matches.", "माल डाला गया! खरीदार मिलने पर सूचना देंगे।", "ಪೋಸ್ಟ್ ಆಯಿತು! ಖರೀದಿದಾರ ಸಿಕ್ಕಾಗ ತಿಳಿಸುತ್ತೇವೆ."],
  queued_offline: ["You're offline. Saved — it will post when you're back online.", "आप ऑफ़लाइन हैं। सहेजा गया — नेटवर्क आने पर भेजेंगे।", "ನೀವು ಆಫ್‌ಲೈನ್‌ನಲ್ಲಿದ್ದೀರಿ. ಉಳಿಸಲಾಗಿದೆ — ನೆಟ್‌ವರ್ಕ್ ಬಂದಾಗ ಕಳುಹಿಸುತ್ತೇವೆ."],
  offline: ["Offline — showing saved data", "ऑफ़लाइन — सहेजा हुआ डेटा", "ಆಫ್‌ಲೈನ್ — ಉಳಿಸಿದ ಮಾಹಿತಿ"],
  pending_sync: ["{n} waiting to sync", "{n} भेजना बाकी", "{n} ಕಳುಹಿಸಲು ಬಾಕಿ"],
  matches: ["Buyer matches", "खरीदार", "ಖರೀದಿದಾರರು"],
  accept: ["Accept", "स्वीकार", "ಒಪ್ಪಿಕೊಳ್ಳಿ"],
  reject: ["Decline", "मना करें", "ನಿರಾಕರಿಸಿ"],
  waiting_buyer: ["You accepted — waiting for buyer", "आपने स्वीकार किया — खरीदार की प्रतीक्षा", "ನೀವು ಒಪ್ಪಿದ್ದೀರಿ — ಖರೀದಿದಾರರಿಗಾಗಿ ಕಾಯುತ್ತಿದೆ"],
  deal_done: ["Deal confirmed", "सौदा पक्का", "ಒಪ್ಪಂದ ಖಚಿತ"],
  call: ["Call", "कॉल करें", "ಕರೆ ಮಾಡಿ"],
  no_lots: ["No lots yet. Get a recommendation, then find a buyer.", "अभी कोई माल नहीं। पहले सलाह लें, फिर खरीदार खोजें।", "ಇನ್ನೂ ಸರಕು ಇಲ್ಲ. ಸಲಹೆ ಪಡೆದು ಖರೀದಿದಾರರನ್ನು ಹುಡುಕಿ."],
  no_matches_yet: ["Looking for buyers…", "खरीदार खोज रहे हैं…", "ಖರೀದಿದಾರರನ್ನು ಹುಡುಕುತ್ತಿದೆ…"],
  no_alerts: ["No alerts yet.", "अभी कोई सूचना नहीं।", "ಇನ್ನೂ ಯಾವುದೇ ಎಚ್ಚರಿಕೆ ಇಲ್ಲ."],
  mark_all_read: ["Mark all read", "सब पढ़ लिया", "ಎಲ್ಲಾ ಓದಿದೆ"],
  left: ["{n} qtl left", "{n} क्विं. बाकी", "{n} ಕ್ವಿಂ ಬಾಕಿ"],
  cancel: ["Cancel", "रद्द करें", "ರದ್ದುಮಾಡಿ"],
  split_title: ["Big lot? Split it across mandis", "ज़्यादा माल? मंडियों में बाँटें", "ಹೆಚ್ಚು ಸರಕು? ಮಂಡಿಗಳಿಗೆ ಹಂಚಿ"],
  loading: ["Loading…", "लोड हो रहा है…", "ಲೋಡ್ ಆಗುತ್ತಿದೆ…"],
  error: ["Something went wrong. Try again.", "कुछ गलत हुआ। फिर कोशिश करें।", "ಏನೋ ತಪ್ಪಾಗಿದೆ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ."],
  language: ["Language", "भाषा", "ಭಾಷೆ"],
  status_open: ["Open", "खुला", "ತೆರೆದಿದೆ"],
  status_partially_matched: ["Partly matched", "आंशिक", "ಭಾಗಶಃ"],
  status_matched: ["Matched", "मिल गया", "ಹೊಂದಿಕೆಯಾಗಿದೆ"],
  status_sold: ["Sold", "बिक गया", "ಮಾರಾಟವಾಗಿದೆ"],
  status_cancelled: ["Cancelled", "रद्द", "ರದ್ದಾಗಿದೆ"],
  status_proposed: ["New offer", "नया प्रस्ताव", "ಹೊಸ ಪ್ರಸ್ತಾಪ"],
  status_accepted: ["Confirmed", "पक्का", "ಖಚಿತ"],
  status_rejected: ["Declined", "मना किया", "ನಿರಾಕರಿಸಲಾಗಿದೆ"],
  km: ["{n} km", "{n} किमी", "{n} ಕಿ.ಮೀ"],
  hello: ["Hello, {name}", "नमस्ते, {name}", "ನಮಸ್ಕಾರ, {name}"],
};
const IDX: Record<Lang, number> = { en: 0, hi: 1, kn: 2 };

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>) {
  const row = D[key];
  let s = row ? row[IDX[lang]] || row[0] : key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (k: string, v?: Record<string, string | number>) => string };
const I18nCtx = createContext<Ctx>({ lang: "en", setLang: () => {}, t: (k) => k });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("lang") as Lang | null;
      if (saved && saved in IDX) setLangState(saved);
      else if (navigator.language.startsWith("kn")) setLangState("kn");
      else if (navigator.language.startsWith("hi")) setLangState("hi");
    } catch {}
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("lang", l);
    } catch {}
  }, []);
  const t = useCallback((k: string, v?: Record<string, string | number>) => translate(lang, k, v), [lang]);
  return <I18nCtx.Provider value={{ lang, setLang, t }}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);

export function cropName(c: { name_en: string; name_hi: string; name_kn: string } | undefined, lang: Lang) {
  if (!c) return "";
  return lang === "hi" ? c.name_hi : lang === "kn" ? c.name_kn : c.name_en;
}

export const inr = (n: number | null | undefined) =>
  n == null ? "—" : "₹" + Math.round(n).toLocaleString("en-IN");
