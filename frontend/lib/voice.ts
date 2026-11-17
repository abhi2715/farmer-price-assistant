"use client";
// Web Speech API helpers: speech-to-text for crop + quantity, text-to-speech for results.
import type { Lang } from "./i18n";

const SPEECH_LANG: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };

export const canListen = () =>
  typeof window !== "undefined" && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;

export function listen(lang: Lang, onText: (t: string) => void, onEnd: () => void): () => void {
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!SR) {
    onEnd();
    return () => {};
  }
  const r = new SR();
  r.lang = SPEECH_LANG[lang];
  r.interimResults = false;
  r.maxAlternatives = 3;
  r.onresult = (e: any) => {
    const alts = Array.from(e.results[0] as ArrayLike<{ transcript: string }>).map((a) => a.transcript);
    onText(alts.join(" | "));
  };
  r.onerror = onEnd;
  r.onend = onEnd;
  r.start();
  return () => r.abort();
}

export function speak(text: string, lang: Lang) {
  if (!canSpeak()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/₹/g, lang === "en" ? "rupees " : "₹"));
  u.lang = SPEECH_LANG[lang];
  const v = synth.getVoices().find((x) => x.lang === u.lang) || synth.getVoices().find((x) => x.lang.startsWith(lang));
  if (v) u.voice = v;
  u.rate = 0.95;
  synth.speak(u);
}

// ---- parsing "tomato 20 quintal" / "टमाटर बीस क्विंटल" / "ಟೊಮೆಟೊ ಇಪ್ಪತ್ತು ಕ್ವಿಂಟಾಲ್" ----
const NUM_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, fifteen: 15,
  twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90, hundred: 100,
  एक: 1, दो: 2, तीन: 3, चार: 4, पांच: 5, पाँच: 5, छह: 6, सात: 7, आठ: 8, नौ: 9, दस: 10, पंद्रह: 15, बीस: 20,
  तीस: 30, चालीस: 40, पचास: 50, साठ: 60, सत्तर: 70, अस्सी: 80, नब्बे: 90, सौ: 100,
  ಒಂದು: 1, ಎರಡು: 2, ಮೂರು: 3, ನಾಲ್ಕು: 4, ಐದು: 5, ಆರು: 6, ಏಳು: 7, ಎಂಟು: 8, ಒಂಬತ್ತು: 9, ಹತ್ತು: 10,
  ಹದಿನೈದು: 15, ಇಪ್ಪತ್ತು: 20, ಮೂವತ್ತು: 30, ನಲವತ್ತು: 40, ಐವತ್ತು: 50, ಅರವತ್ತು: 60, ಎಪ್ಪತ್ತು: 70, ಎಂಬತ್ತು: 80, ತೊಂಬತ್ತು: 90, ನೂರು: 100,
};
const DEVANAGARI_DIGITS = "०१२३४५६७८९";
const KANNADA_DIGITS = "೦೧೨೩೪೫೬೭೮೯";

export function parseQuantity(text: string): number | null {
  const norm = text
    .replace(/[०-९]/g, (d) => String(DEVANAGARI_DIGITS.indexOf(d)))
    .replace(/[೦-೯]/g, (d) => String(KANNADA_DIGITS.indexOf(d)));
  const m = norm.match(/\d+(\.\d+)?/);
  if (m) return parseFloat(m[0]);
  let total = 0;
  for (const w of norm.toLowerCase().split(/[\s|,]+/)) if (w in NUM_WORDS) total += NUM_WORDS[w];
  return total || null;
}

export function parseCrop<C extends { id: number; code: string; name_en: string; name_hi: string; name_kn: string }>(
  text: string, crops: C[],
): C | null {
  const s = text.toLowerCase();
  const aliases: Record<string, string[]> = {
    tomato: ["tamatar", "टमाटर", "ಟೊಮ್ಯಾಟೊ", "ಟೊಮೇಟೊ"], onion: ["pyaz", "kanda", "ಉಳ್ಳಾಗಡ್ಡಿ"],
    potato: ["aloo", "batata"], paddy: ["rice", "dhan", "ಅಕ್ಕಿ"], maize: ["corn", "makka"],
    tur: ["arhar", "toor", "red gram", "ತೊಗರಿ ಬೇಳೆ"], green_chilli: ["chilli", "mirchi", "ಮೆಣಸಿನಕಾಯಿ"],
    banana: ["kela", "ಬಾಳೆ"], ragi: ["finger millet", "ರಾಗಿ"], cotton: ["kapas", "ಹತ್ತಿ"],
  };
  for (const c of crops) {
    const names = [c.name_en, c.name_hi, c.name_kn, c.code.replace("_", " "), ...(aliases[c.code] || [])];
    if (names.some((n) => n && s.includes(n.toLowerCase().split(" (")[0]))) return c;
  }
  return null;
}
