"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Badge, Button, Card, Stat } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { cropName, inr, useI18n } from "@/lib/i18n";

type Crop = { id: number; name_en: string; name_hi: string; name_kn: string; emoji: string };
type Demand = { id: number; emoji: string; crop: string; min_grade: string; quantity_qtl: number; remaining_qtl: number; max_price: number; max_distance_km: number; needed_by: string; status: string };
type Match = {
  id: number; status: string; crop: string; emoji: string; grade: string; quantity_qtl: number; price_per_qtl: number; value: number;
  distance_km: number; transport_per_qtl: number; score: number; farmer_accepted: boolean; buyer_accepted: boolean;
  farmer: { name: string; village: string; phone?: string };
};
type Route = { total_km: number; depot: { lat: number; lon: number; name: string }; stops: { match_id: number; crop: string; quantity_qtl: number; farmer: string; village: string; lat: number; lon: number; status: string }[] };
type Tx = { id: number; crop: string; quantity_qtl: number; price_per_qtl: number; gross_amount: number; buyer_commission: number; buyer_total: number; created_at: string };

export default function Buyer() {
  const { lang } = useI18n();
  const [crops, setCrops] = useState<Crop[]>([]);
  const [demands, setDemands] = useState<Demand[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [route, setRoute] = useState<Route | null>(null);
  const [txs, setTxs] = useState<Tx[]>([]);
  const [form, setForm] = useState({ crop_id: 1, min_grade: "B", quantity_qtl: "50", max_price: "", max_distance_km: "150" });
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    api<Demand[]>("/demands/mine").then(setDemands).catch(() => {});
    api<Match[]>("/matches/mine").then(setMatches).catch(() => {});
    api<Route>("/buyer/route").then(setRoute).catch(() => {});
    api<Tx[]>("/transactions/mine").then(setTxs).catch(() => {});
  }, []);
  useEffect(() => {
    api<Crop[]>("/crops").then(setCrops).catch(() => {});
    load();
  }, [load]);

  const post = async () => {
    setMsg("");
    try {
      const r = await api<{ matches: Match[] }>("/demands", {
        method: "POST",
        body: { crop_id: +form.crop_id, min_grade: form.min_grade, quantity_qtl: +form.quantity_qtl, max_price: +form.max_price, max_distance_km: +form.max_distance_km },
      });
      setMsg(`Demand posted · ${r.matches.length} lot(s) matched right away`);
      load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "Offline — try again");
    }
  };
  const respond = async (id: number, accept: boolean) => {
    await api(`/matches/${id}/respond`, { method: "POST", body: { accept } }).catch(() => {});
    load();
  };

  const pending = matches.filter((m) => m.status === "proposed");
  const spend = txs.reduce((s, t) => s + t.buyer_total, 0);

  return (
    <AppShell role="buyer" title="AgriRoute · Buyer">
      <h1 className="text-3xl font-bold tracking-tight">Sourcing dashboard</h1>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Open demands" value={demands.filter((d) => ["open", "partially_matched"].includes(d.status)).length} />
        <Stat label="Offers to review" value={pending.filter((m) => !m.buyer_accepted).length} />
        <Stat label="Confirmed deals" value={txs.length} />
        <Stat label="Total spend" value={inr(spend)} sub="incl. platform fee" />
      </div>

      <Card className="mt-6">
        <h2 className="text-lg font-bold">Post a demand</h2>
        <form className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); post(); }}>
          <label className="flex flex-col gap-1">Crop
            <select value={form.crop_id} onChange={(e) => setForm({ ...form, crop_id: +e.target.value })}>
              {crops.map((c) => <option key={c.id} value={c.id}>{c.emoji} {cropName(c, lang)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">Min grade
            <select value={form.min_grade} onChange={(e) => setForm({ ...form, min_grade: e.target.value })}>
              {["A", "B", "C"].map((g) => <option key={g}>{g}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">Quantity (qtl)
            <input type="number" min={1} required value={form.quantity_qtl} onChange={(e) => setForm({ ...form, quantity_qtl: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">Max landed price ₹/qtl
            <input type="number" min={1} required value={form.max_price} onChange={(e) => setForm({ ...form, max_price: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1">Max distance (km)
            <input type="number" min={1} value={form.max_distance_km} onChange={(e) => setForm({ ...form, max_distance_km: e.target.value })} />
          </label>
          <div className="flex items-end"><Button className="w-full" disabled={!form.max_price}>Post demand</Button></div>
        </form>
        {msg && <p className="mt-3 text-sm text-leaf-700">{msg}</p>}
      </Card>

      <h2 className="mt-8 text-xl font-bold">Matched lots</h2>
      <div className="mt-3 flex flex-col gap-3">
        {matches.length === 0 && <p className="text-soil-500">No matches yet — post a demand.</p>}
        {matches.map((m) => (
          <Card key={m.id}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-bold">{m.emoji} {m.crop} · grade {m.grade} · {m.quantity_qtl} qtl</div>
                <div className="text-sm text-soil-500">
                  {m.farmer.name}, {m.farmer.village} · {Math.round(m.distance_km)} km · transport ≈ {inr(m.transport_per_qtl)}/qtl · match score {(m.score * 100).toFixed(0)}
                </div>
                <div className="mt-1">{inr(m.price_per_qtl)}/qtl · <b>{inr(m.value)}</b></div>
              </div>
              <Badge kind={m.status}>{m.status === "proposed" && m.buyer_accepted ? "awaiting farmer" : m.status}</Badge>
            </div>
            {m.status === "proposed" && !m.buyer_accepted && (
              <div className="mt-3 flex gap-2">
                <Button onClick={() => respond(m.id, true)}>Accept</Button>
                <Button variant="danger" onClick={() => respond(m.id, false)}>Decline</Button>
              </div>
            )}
            {m.status === "accepted" && m.farmer.phone && <a className="mt-2 inline-block font-semibold text-leaf-700" href={`tel:+91${m.farmer.phone}`}>📞 +91 {m.farmer.phone}</a>}
          </Card>
        ))}
      </div>

      {route && route.stops.length > 0 && (
        <Card className="mt-8">
          <h2 className="text-lg font-bold">Pickup route · {route.total_km} km round trip</h2>
          <p className="text-xs text-soil-400">Optimised with OR-Tools (TSP) from {route.depot.name}</p>
          <RouteMap route={route} />
          <ol className="mt-3 list-decimal pl-5 text-sm">
            {route.stops.map((s) => <li key={s.match_id} className="py-0.5">{s.farmer} ({s.village}) — {s.crop}, {s.quantity_qtl} qtl <span className="text-soil-400">· {s.status}</span></li>)}
          </ol>
        </Card>
      )}

      <h2 className="mt-8 text-xl font-bold">My demands</h2>
      <div className="mt-3 overflow-x-auto rounded-3xl bg-white">
        <table className="w-full text-left text-sm">
          <thead className="text-soil-500"><tr><th className="p-3">Crop</th><th>Qty</th><th>Left</th><th>Max ₹</th><th>By</th><th>Status</th></tr></thead>
          <tbody>
            {demands.map((d) => (
              <tr key={d.id} className="border-t border-soil-100">
                <td className="p-3">{d.emoji} {d.crop} ({d.min_grade}+)</td><td>{d.quantity_qtl}</td><td>{d.remaining_qtl}</td>
                <td>{inr(d.max_price)}</td><td>{d.needed_by}</td><td><Badge kind={d.status}>{d.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {txs.length > 0 && (
        <>
          <h2 className="mt-8 text-xl font-bold">Transactions</h2>
          <div className="mt-3 overflow-x-auto rounded-3xl bg-white">
            <table className="w-full text-left text-sm">
              <thead className="text-soil-500"><tr><th className="p-3">#</th><th>Crop</th><th>Qty</th><th>Price</th><th>Value</th><th>Fee</th><th>Total</th></tr></thead>
              <tbody>
                {txs.map((t) => (
                  <tr key={t.id} className="border-t border-soil-100">
                    <td className="p-3">{t.id}</td><td>{t.crop}</td><td>{t.quantity_qtl}</td><td>{inr(t.price_per_qtl)}</td>
                    <td>{inr(t.gross_amount)}</td><td>{inr(t.buyer_commission)}</td><td className="font-semibold">{inr(t.buyer_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </AppShell>
  );
}

function RouteMap({ route }: { route: Route }) {
  const pts = [route.depot, ...route.stops];
  const lats = pts.map((p) => p.lat), lons = pts.map((p) => p.lon);
  const [a, b, c, d] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const W = 600, H = 260, P = 24;
  const x = (lon: number) => P + ((lon - c) / Math.max(d - c, 0.01)) * (W - 2 * P);
  const y = (lat: number) => H - P - ((lat - a) / Math.max(b - a, 0.01)) * (H - 2 * P);
  const path = [...pts, route.depot].map((p, i) => `${i ? "L" : "M"}${x(p.lon)},${y(p.lat)}`).join("");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full rounded-2xl bg-leaf-50" role="img" aria-label="Pickup route">
      <path d={path} fill="none" stroke="#16a34a" strokeWidth="2.5" strokeDasharray="6 4" />
      <rect x={x(route.depot.lon) - 7} y={y(route.depot.lat) - 7} width="14" height="14" rx="3" fill="#1c1917" />
      {route.stops.map((s, i) => (
        <g key={s.match_id}>
          <circle cx={x(s.lon)} cy={y(s.lat)} r="11" fill="#16a34a" />
          <text x={x(s.lon)} y={y(s.lat) + 4} textAnchor="middle" fontSize="12" fill="#fff" fontWeight="700">{i + 1}</text>
        </g>
      ))}
    </svg>
  );
}
