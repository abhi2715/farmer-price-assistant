"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { ApiError, api, postOrQueue } from "@/lib/api";
import { cropName, inr, useI18n } from "@/lib/i18n";

type Crop = { id: number; name_en: string; name_hi: string; name_kn: string; emoji: string };
type M = {
  id: number; status: string; quantity_qtl: number; price_per_qtl: number; distance_km: number; value: number;
  farmer_accepted: boolean; buyer_accepted: boolean; buyer: { name: string; type: string; phone?: string };
};
type Lot = {
  id: number; crop_id: number; emoji: string; grade: string; quantity_qtl: number; remaining_qtl: number;
  ask_price: number; status: string; created_at: string; matches: M[];
};

export default function Lots() {
  const { t, lang } = useI18n();
  const [crops, setCrops] = useState<Crop[]>([]);
  const [lots, setLots] = useState<Lot[] | null>(null);
  const [form, setForm] = useState({ crop_id: 0, grade: "B", quantity_qtl: "", ask_price: "" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<Lot[]>("/lots/mine").then(setLots).catch(() => setLots([])), []);
  useEffect(() => {
    api<Crop[]>("/crops").then((cs) => {
      setCrops(cs);
      const q = new URLSearchParams(location.search);
      setForm((f) => ({ ...f, crop_id: +(q.get("crop") || cs[0]?.id || 0), quantity_qtl: q.get("qty") || "", ask_price: q.get("price") || "" }));
    });
    load();
  }, [load]);

  const submit = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await postOrQueue<{ matches: M[] }>("/lots", {
        crop_id: form.crop_id, grade: form.grade, quantity_qtl: +form.quantity_qtl, ask_price: +form.ask_price,
      });
      if ("queued" in r) setMsg(t("queued_offline"));
      else setMsg(r.matches.length ? t("posted_matched", { n: r.matches.length }) : t("posted_waiting"));
      setForm((f) => ({ ...f, quantity_qtl: "", ask_price: "" }));
      history.replaceState(null, "", "/farmer/lots/");
      load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  };

  const respond = async (id: number, accept: boolean) => {
    await api(`/matches/${id}/respond`, { method: "POST", body: { accept } }).catch(() => {});
    load();
  };
  const cancel = async (id: number) => {
    await api(`/lots/${id}`, { method: "DELETE" }).catch(() => {});
    load();
  };
  const cropOf = (id: number) => crops.find((c) => c.id === id);

  return (
    <AppShell role="farmer">
      <h1 className="text-3xl font-bold tracking-tight">{t("new_lot")}</h1>
      <Card className="mt-4">
        <form className="grid grid-cols-2 gap-3" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label className="col-span-2 flex flex-col gap-1">{t("crop")}
            <select value={form.crop_id} onChange={(e) => setForm({ ...form, crop_id: +e.target.value })}>
              {crops.map((c) => <option key={c.id} value={c.id}>{c.emoji} {cropName(c, lang)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">{t("quintal")}
            <input required type="number" inputMode="decimal" min={0.5} step="0.5" value={form.quantity_qtl}
              onChange={(e) => setForm({ ...form, quantity_qtl: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">{t("grade")}
            <select value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })}>
              {["A", "B", "C"].map((g) => <option key={g}>{g}</option>)}
            </select>
          </label>
          <label className="col-span-2 flex flex-col gap-1">{t("ask_price")}
            <input required type="number" inputMode="numeric" min={1} value={form.ask_price}
              onChange={(e) => setForm({ ...form, ask_price: e.target.value })} />
          </label>
          <Button className="col-span-2" disabled={busy || !form.quantity_qtl || !form.ask_price}>{t("post_lot")}</Button>
        </form>
        {msg && <p className="mt-3 rounded-2xl bg-leaf-50 p-3 text-center text-leaf-700" role="status">{msg}</p>}
      </Card>

      <h2 className="mt-8 text-xl font-bold">{t("nav_lots")}</h2>
      {lots === null && <Spinner />}
      {lots?.length === 0 && <p className="mt-3 text-soil-500">{t("no_lots")}</p>}
      <div className="mt-3 flex flex-col gap-3">
        {lots?.map((l) => (
          <Card key={l.id}>
            <div className="flex items-start justify-between">
              <div>
                <div className="text-lg font-bold">{l.emoji} {cropName(cropOf(l.crop_id), lang)} · {l.quantity_qtl} {t("qtl")}</div>
                <div className="text-sm text-soil-500">{t("grade")} {l.grade} · {inr(l.ask_price)}/{t("qtl")} · {t("left", { n: l.remaining_qtl })}</div>
              </div>
              <Badge kind={l.status}>{t(`status_${l.status}`)}</Badge>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              {l.matches.length === 0 && ["open", "partially_matched"].includes(l.status) && <p className="text-sm text-soil-400">{t("no_matches_yet")}</p>}
              {l.matches.map((m) => (
                <div key={m.id} className="rounded-2xl bg-soil-50 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">🏪 {m.buyer.name}</span>
                    <Badge kind={m.status}>{t(`status_${m.status}`)}</Badge>
                  </div>
                  <div className="mt-1 text-sm text-soil-700">
                    {m.quantity_qtl} {t("qtl")} × <b>{inr(m.price_per_qtl)}</b> = <b>{inr(m.value)}</b> · {t("km", { n: Math.round(m.distance_km) })}
                  </div>
                  {m.status === "proposed" && !m.farmer_accepted && (
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <Button onClick={() => respond(m.id, true)}>{t("accept")}</Button>
                      <Button variant="danger" onClick={() => respond(m.id, false)}>{t("reject")}</Button>
                    </div>
                  )}
                  {m.status === "proposed" && m.farmer_accepted && <p className="mt-1 text-sm text-amber-700">{t("waiting_buyer")}</p>}
                  {m.status === "accepted" && m.buyer.phone && (
                    <a href={`tel:+91${m.buyer.phone}`} className="mt-2 block rounded-2xl bg-leaf-600 py-2.5 text-center font-semibold text-white">📞 {t("call")} +91 {m.buyer.phone}</a>
                  )}
                </div>
              ))}
            </div>
            {["open", "partially_matched"].includes(l.status) && (
              <button onClick={() => cancel(l.id)} className="mt-3 text-sm text-soil-400">{t("cancel")}</button>
            )}
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
