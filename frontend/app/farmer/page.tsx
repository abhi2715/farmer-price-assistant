"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { ApiError, api, session } from "@/lib/api";
import { cropName, inr, useI18n } from "@/lib/i18n";
import { canListen, canSpeak, listen, parseCrop, parseQuantity, speak } from "@/lib/voice";

type Crop = { id: number; code: string; name_en: string; name_hi: string; name_kn: string; emoji: string; perishable: boolean };
type Opt = {
  mandi_id: number; mandi_name: string; sell_date: string; days_wait: number; distance_km: number; price: number;
  price_lo: number; gross: number; transport: number; vehicle: string; fees: number; spoilage_pct: number;
  spoilage_loss: number; holding_cost: number; net: number; net_lo: number; net_per_qtl: number;
};
type Rec = {
  best: Opt; baseline: Opt | null; gain_vs_baseline: number | null; best_per_mandi: Opt[]; explanation: string[];
  why_price: { reasons: { text: string; direction: string; impact_pct: number }[]; method?: string };
  split_plan: { allocations: { mandi_name: string; quantity_qtl: number; sell_date: string; net: number }[]; total_net: number } | null;
  model: string; as_of: string;
};

const PRESETS = [5, 10, 20, 50, 100];

export default function FarmerHome() {
  const { t, lang } = useI18n();
  const [crops, setCrops] = useState<Crop[]>([]);
  const [crop, setCrop] = useState<Crop | null>(null);
  const [qty, setQty] = useState<number | null>(null);
  const [rec, setRec] = useState<Rec | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [hearing, setHearing] = useState(false);
  const [heard, setHeard] = useState("");

  useEffect(() => {
    api<Crop[]>("/crops").then((cs) => {
      const mine = new Set(session.user()?.farmer?.crop_ids || []);
      setCrops([...cs].sort((a, b) => Number(mine.has(b.id)) - Number(mine.has(a.id))));
    }).catch(() => setErr(t("error")));
  }, [t]);

  const go = async (c: Crop, q: number) => {
    setBusy(true);
    setErr("");
    setRec(null);
    try {
      setRec(await api<Rec>(`/recommend?lang=${lang}`, { method: "POST", body: { crop_id: c.id, quantity_qtl: q } }));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("offline"));
    } finally {
      setBusy(false);
    }
  };
  // Re-fetch explanation in the new language if the user switches language on the result screen.
  useEffect(() => {
    if (rec && crop && qty) go(crop, qty);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const voice = () => {
    setHearing(true);
    setHeard("");
    listen(lang, (text) => {
      setHeard(text.split(" | ")[0]);
      const c = parseCrop(text, crops);
      const q = parseQuantity(text);
      if (c) setCrop(c);
      if (q) setQty(q);
      if (c && q) go(c, q);
    }, () => setHearing(false));
  };

  const reset = () => {
    setCrop(null);
    setQty(null);
    setRec(null);
    setErr("");
  };
  const step = rec || busy ? 2 : crop ? 1 : 0;
  const user = session.user();

  return (
    <AppShell role="farmer">
      {/* progress */}
      <div className="mb-4 flex gap-1.5" aria-hidden>
        {[0, 1, 2].map((i) => <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-leaf-500" : "bg-soil-100"}`} />)}
      </div>

      {step === 0 && (
        <section className="animate-rise">
          {user?.name && <p className="text-soil-500">{t("hello", { name: user.name.split(" ")[0] })}</p>}
          <h1 className="text-3xl font-bold tracking-tight">{t("step_crop")}</h1>
          {canListen() && (
            <button onClick={voice} className={`mt-4 flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left ${hearing ? "bg-red-50 text-red-700" : "bg-leaf-50 text-leaf-700"}`}>
              <span className={`grid h-10 w-10 place-items-center rounded-full ${hearing ? "animate-pulse bg-red-500" : "bg-leaf-600"} text-white`}>🎤</span>
              <span>
                <span className="block font-semibold">{hearing ? t("listening") : t("speak")}</span>
                <span className="text-sm opacity-80">{heard || t("voice_hint")}</span>
              </span>
            </button>
          )}
          {!crops.length && !err && <Spinner />}
          <div className="mt-4 grid grid-cols-3 gap-3">
            {crops.map((c) => (
              <button key={c.id} onClick={() => setCrop(c)}
                className="flex aspect-square flex-col items-center justify-center gap-1 rounded-3xl bg-white p-2 shadow-sm active:scale-95 transition-transform">
                <span className="text-4xl" aria-hidden>{c.emoji}</span>
                <span className="text-center text-sm font-semibold leading-tight">{cropName(c, lang)}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {step === 1 && crop && (
        <section className="animate-rise">
          <button onClick={reset} className="text-sm text-soil-500">← {crop.emoji} {cropName(crop, lang)}</button>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">{t("step_qty")}</h1>
          <div className="mt-5 grid grid-cols-3 gap-3">
            {PRESETS.map((p) => (
              <button key={p} onClick={() => setQty(p)} aria-pressed={qty === p}
                className={`rounded-3xl py-6 text-center shadow-sm transition ${qty === p ? "bg-leaf-600 text-white" : "bg-white"}`}>
                <span className="block text-3xl font-bold">{p}</span>
                <span className="text-xs opacity-80">{t("quintal")}</span>
              </button>
            ))}
            <label className="flex flex-col justify-center rounded-3xl bg-white px-3 shadow-sm">
              <span className="sr-only">{t("quintal")}</span>
              <input type="number" inputMode="decimal" min={0.5} max={10000} placeholder="…"
                value={qty && !PRESETS.includes(qty) ? qty : ""} onChange={(e) => setQty(e.target.value ? +e.target.value : null)}
                className="w-full border-0 p-0 text-center text-3xl font-bold focus:ring-0" />
              <span className="text-center text-xs text-soil-500">{t("quintal")}</span>
            </label>
          </div>
          <Button className="mt-6 w-full text-lg" disabled={!qty || qty <= 0} onClick={() => qty && go(crop, qty)}>
            {t("show_best")} →
          </Button>
        </section>
      )}

      {step === 2 && (
        <section>
          {busy && <Spinner label={t("loading")} />}
          {err && <Card className="text-center text-red-600">{err}</Card>}
          {rec && crop && qty && <Result rec={rec} crop={crop} qty={qty} onReset={reset} />}
        </section>
      )}
      {step !== 2 && err && <p className="mt-4 text-center text-red-600">{err}</p>}
    </AppShell>
  );
}

function Result({ rec, crop, qty, onReset }: { rec: Rec; crop: Crop; qty: number; onReset: () => void }) {
  const { t, lang } = useI18n();
  const b = rec.best;
  const when = b.days_wait === 0 ? t("today") : t("in_days", { n: b.days_wait });
  const dateStr = new Date(b.sell_date).toLocaleDateString(lang === "en" ? "en-IN" : `${lang}-IN`, { weekday: "short", day: "numeric", month: "short" });
  const ask = Math.ceil(b.net_per_qtl / 10) * 10;
  const say = useMemo(() => [`${b.mandi_name}. ${when}. ${t("you_get")} ${inr(b.net)}.`, ...rec.explanation].join(" "), [b, when, rec, t]);

  return (
    <div className="flex flex-col gap-4">
      <Card className="animate-rise overflow-hidden !p-0">
        <div className="bg-gradient-to-br from-leaf-600 to-leaf-700 p-6 text-white">
          <div className="flex items-center justify-between text-sm opacity-90">
            <span>{t("best_option")} · {crop.emoji} {cropName(crop, lang)} · {qty} {t("qtl")}</span>
            {canSpeak() && (
              <button onClick={() => speak(say, lang)} className="rounded-full bg-white/20 px-3 py-1 font-semibold">🔊 {t("listen")}</button>
            )}
          </div>
          <div className="mt-4 text-4xl font-bold leading-tight tracking-tight">{b.mandi_name}</div>
          <div className="mt-1 text-lg opacity-95">{when} · {dateStr} · {t("km", { n: Math.round(b.distance_km) })}</div>
          <div className="mt-5 text-sm opacity-80">{t("you_get")}</div>
          <div className="text-5xl font-bold tracking-tight">{inr(b.net)}</div>
          {!!rec.gain_vs_baseline && rec.gain_vs_baseline > 0 && (
            <div className="mt-2 inline-block rounded-full bg-white/20 px-3 py-1 text-sm font-semibold">+ {t("more_than_nearest", { n: Math.round(rec.gain_vs_baseline).toLocaleString("en-IN") })}</div>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 p-5 text-sm">
          <dt className="text-soil-500">{t("price_per_qtl")}</dt><dd className="text-right font-semibold">{inr(b.price)}</dd>
          <dt className="text-soil-500">{t("gross")}</dt><dd className="text-right">{inr(b.gross)}</dd>
          <dt className="text-soil-500">− {t("transport")}</dt><dd className="text-right">{inr(b.transport)}</dd>
          <dt className="text-soil-500">− {t("fees")}</dt><dd className="text-right">{inr(b.fees)}</dd>
          <dt className="text-soil-500">− {t("spoilage")} ({b.spoilage_pct.toFixed(1)}%)</dt><dd className="text-right">{inr(b.spoilage_loss)}</dd>
          {b.holding_cost > 0 && <><dt className="text-soil-500">− {t("holding")}</dt><dd className="text-right">{inr(b.holding_cost)}</dd></>}
          <dt className="border-t border-soil-100 pt-2 font-semibold">{t("net")}</dt><dd className="border-t border-soil-100 pt-2 text-right font-bold text-leaf-700">{inr(b.net)}</dd>
          <dt className="text-soil-500">{t("worst_case")}</dt><dd className="text-right text-soil-500">{inr(b.net_lo)}</dd>
        </dl>
      </Card>

      <Card className="animate-rise [animation-delay:80ms]">
        <h2 className="font-bold">{t("why")}</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {rec.explanation.map((l, i) => <li key={i} className="flex gap-2 text-[15px] leading-snug"><span className="text-leaf-600">●</span>{l}</li>)}
        </ul>
        {rec.why_price?.reasons?.length > 0 && (
          <>
            <h3 className="mt-5 text-sm font-semibold text-soil-500">{t("why_price")}</h3>
            <ul className="mt-2 flex flex-col gap-2">
              {rec.why_price.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-[15px] leading-snug">
                  <span className={r.direction === "up" ? "text-leaf-600" : "text-red-500"}>{r.direction === "up" ? "▲" : "▼"}</span>
                  <span>{r.text} <span className="text-soil-400">({r.impact_pct > 0 ? "+" : ""}{r.impact_pct}%)</span></span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-soil-400">{rec.why_price.method} · {rec.model}</p>
          </>
        )}
      </Card>

      {rec.split_plan && (
        <Card className="animate-rise border border-amber-200 bg-amber-50/50">
          <h2 className="font-bold">{t("split_title")}</h2>
          <ul className="mt-2 text-sm">
            {rec.split_plan.allocations.map((a, i) => (
              <li key={i} className="flex justify-between py-1"><span>{a.mandi_name} · {a.sell_date}</span><span>{a.quantity_qtl} {t("qtl")}</span></li>
            ))}
          </ul>
          <p className="mt-2 text-right font-bold">{inr(rec.split_plan.total_net)}</p>
        </Card>
      )}

      <Link href={`/farmer/lots/?crop=${crop.id}&qty=${qty}&price=${ask}`}
        className="block rounded-2xl bg-soil-900 py-4 text-center text-lg font-semibold text-white">
        🤝 {t("find_buyer")} · {inr(ask)}/{t("qtl")}
      </Link>

      <Card>
        <h2 className="font-bold">{t("other_options")}</h2>
        <ul className="mt-2 divide-y divide-soil-100">
          {rec.best_per_mandi.map((o) => (
            <li key={o.mandi_id} className="flex items-center justify-between py-2.5 text-sm">
              <span>
                <span className="font-semibold">{o.mandi_name}</span>
                <span className="block text-soil-500">{o.days_wait === 0 ? t("today") : t("in_days", { n: o.days_wait })} · {t("km", { n: Math.round(o.distance_km) })} · {inr(o.price)}/{t("qtl")}</span>
              </span>
              <span className="text-right font-semibold">{inr(o.net)}{o.mandi_id === b.mandi_id && <> <Badge kind="accepted">★</Badge></>}</span>
            </li>
          ))}
        </ul>
      </Card>
      <Button variant="ghost" onClick={onReset}>↺ {t("start_over")}</Button>
    </div>
  );
}
