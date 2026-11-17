"use client";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import ForecastChart from "@/components/ForecastChart";
import { Card, Spinner } from "@/components/ui";
import { ApiError, api, session } from "@/lib/api";
import { cropName, inr, useI18n } from "@/lib/i18n";

type Crop = { id: number; name_en: string; name_hi: string; name_kn: string; emoji: string };
type Mandi = { id: number; name: string; distance_km?: number };
type FC = {
  model: string; origin_date: string; last_price: number; interval: string;
  history: { date: string; modal: number }[]; forecast: { date: string; yhat: number; lo: number; hi: number; horizon: number }[];
  summary: Record<string, { yhat: number; lo: number; hi: number; change_pct: number; mape: number | null }>;
  why: { reasons: { text: string; direction: string; impact_pct: number }[]; method: string } | null;
};

export default function Forecast() {
  const { t, lang } = useI18n();
  const [crops, setCrops] = useState<Crop[]>([]);
  const [crop, setCrop] = useState<number | null>(null);
  const [mandis, setMandis] = useState<Mandi[]>([]);
  const [mandi, setMandi] = useState<number | null>(null);
  const [fc, setFc] = useState<FC | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Crop[]>("/crops").then((cs) => {
      setCrops(cs);
      const mine = session.user()?.farmer?.crop_ids || [];
      setCrop(mine[0] || cs[0]?.id);
    }).catch(() => setErr(t("error")));
  }, [t]);

  useEffect(() => {
    if (!crop) return;
    const f = session.user()?.farmer;
    api<Mandi[]>(`/mandis?crop_id=${crop}${f ? `&lat=${f.lat}&lon=${f.lon}` : ""}`).then((ms) => {
      setMandis(ms);
      setMandi(ms[0]?.id ?? null);
    }).catch(() => setErr(t("error")));
  }, [crop, t]);

  useEffect(() => {
    if (!crop || !mandi) return;
    setFc(null);
    setErr("");
    api<FC>(`/forecasts?crop_id=${crop}&mandi_id=${mandi}&history_days=60&lang=${lang}`)
      .then(setFc).catch((e) => setErr(e instanceof ApiError ? e.message : t("offline")));
  }, [crop, mandi, lang, t]);

  return (
    <AppShell role="farmer">
      <h1 className="text-3xl font-bold tracking-tight">{t("forecast")}</h1>
      <div className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {crops.map((c) => (
          <button key={c.id} onClick={() => setCrop(c.id)} aria-pressed={crop === c.id}
            className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${crop === c.id ? "bg-soil-900 text-white" : "bg-white shadow-sm"}`}>
            {c.emoji} {cropName(c, lang)}
          </button>
        ))}
      </div>
      <label className="mt-4 block">
        <span className="sr-only">{t("mandi")}</span>
        <select value={mandi ?? ""} onChange={(e) => setMandi(+e.target.value)} className="w-full">
          {mandis.map((m) => <option key={m.id} value={m.id}>{m.name}{m.distance_km != null ? ` · ${Math.round(m.distance_km)} km` : ""}</option>)}
        </select>
      </label>
      {err && <Card className="mt-4 text-center text-red-600">{err}</Card>}
      {!fc && !err && <Spinner />}
      {fc && (
        <div className="mt-4 flex flex-col gap-4">
          <Card>
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-soil-500">{t("now")} · {fc.origin_date}</span>
              <span className="text-3xl font-bold">{inr(fc.last_price)}<span className="text-sm font-normal text-soil-500">/{t("qtl")}</span></span>
            </div>
            <div className="mt-3">
              <ForecastChart history={fc.history.map((h) => ({ date: h.date, value: h.modal }))} forecast={fc.forecast} />
            </div>
            <p className="text-xs text-soil-400">— — {t("forecast")} · ▒ {t("range")} ({fc.interval}) · {fc.model}</p>
          </Card>
          <div className="grid grid-cols-3 gap-3">
            {["7", "14", "30"].map((h) => {
              const s = fc.summary[h];
              if (!s) return null;
              return (
                <Card key={h} className="!p-4">
                  <div className="text-xs text-soil-500">{t("days_n", { n: h })}</div>
                  <div className="mt-1 text-xl font-bold">{inr(s.yhat)}</div>
                  <div className={`text-sm font-semibold ${s.change_pct >= 0 ? "text-leaf-600" : "text-red-600"}`}>
                    {s.change_pct >= 0 ? "▲" : "▼"} {Math.abs(s.change_pct)}%
                  </div>
                  <div className="mt-1 text-[11px] leading-tight text-soil-400">{inr(s.lo)}–{inr(s.hi)}</div>
                  {s.mape != null && <div className="text-[11px] text-soil-400">{t("accuracy", { n: s.mape })}</div>}
                </Card>
              );
            })}
          </div>
          {fc.why && fc.why.reasons.length > 0 && (
            <Card>
              <h2 className="font-bold">{t("why_price")} ({t("days_n", { n: 7 })})</h2>
              <ul className="mt-2 flex flex-col gap-2">
                {fc.why.reasons.map((r, i) => (
                  <li key={i} className="flex gap-2 text-[15px]">
                    <span className={r.direction === "up" ? "text-leaf-600" : "text-red-500"}>{r.direction === "up" ? "▲" : "▼"}</span>{r.text}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </AppShell>
  );
}
