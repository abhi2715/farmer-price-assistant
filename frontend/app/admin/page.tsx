"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Badge, Button, Card, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { inr } from "@/lib/i18n";

type Summary = {
  users: Record<string, number>; matches: Record<string, number>; lots_open: number; demands_open: number; transactions: number;
  gmv: number; commission_earned: number; volume_qtl: number; commission_rates: { farmer_pct: number; buyer_pct: number };
  price_rows: number; latest_price_date: string; model: { version: string; best_model: string; mape: Record<string, number>; created_at: string } | null;
};
type Report = { meta: Record<string, any>; mape_by_horizon: Record<string, Record<string, number>>; mape_overall: Record<string, number>; best_model: string; mape_by_crop: Record<string, Record<string, number>> };
const TABS = ["Matches", "Transactions", "Users", "Model", "Data quality"] as const;

export default function Admin() {
  const [s, setS] = useState<Summary | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("Matches");
  const [rows, setRows] = useState<any[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [job, setJob] = useState("");

  const loadSummary = useCallback(() => api<Summary>("/admin/summary").then(setS).catch(() => {}), []);
  useEffect(() => {
    loadSummary();
  }, [loadSummary]);
  useEffect(() => {
    setRows([]);
    if (tab === "Model") api<{ report: Report }>("/admin/model-report").then((r) => setReport(r.report)).catch(() => {});
    else api<any[]>({ Matches: "/admin/matches", Transactions: "/admin/transactions", Users: "/admin/users", "Data quality": "/admin/ingestion-runs" }[tab]).then(setRows).catch(() => {});
  }, [tab]);

  const run = async (name: string) => {
    setJob(`${name}: running…`);
    try {
      const r = await api<{ queued: string }>(`/admin/jobs/${name}`, { method: "POST", timeoutMs: 600000 });
      setJob(`${r.queued}: queued ✓`);
      loadSummary();
    } catch {
      setJob(`${name}: failed`);
    }
  };

  return (
    <AppShell role="admin" title="AgriRoute · Admin">
      <h1 className="text-3xl font-bold tracking-tight">Platform overview</h1>
      {s && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Commission earned" value={inr(s.commission_earned)} sub={`${s.commission_rates.farmer_pct}% farmer + ${s.commission_rates.buyer_pct}% buyer`} />
          <Stat label="GMV" value={inr(s.gmv)} sub={`${s.transactions} deals · ${s.volume_qtl} qtl`} />
          <Stat label="Users" value={Object.values(s.users).reduce((a, b) => a + b, 0)} sub={Object.entries(s.users).map(([k, v]) => `${v} ${k}`).join(" · ")} />
          <Stat label="Matches" value={Object.values(s.matches).reduce((a, b) => a + b, 0)} sub={Object.entries(s.matches).map(([k, v]) => `${v} ${k}`).join(" · ")} />
          <Stat label="Open lots / demands" value={`${s.lots_open} / ${s.demands_open}`} />
          <Stat label="Price rows" value={s.price_rows.toLocaleString("en-IN")} sub={`latest ${s.latest_price_date}`} />
          {s.model && <Stat label="Forecast model" value={s.model.best_model} sub={`${s.model.version} · mean MAPE ${s.model.mape?.[s.model.best_model]?.toFixed(1)}%`} />}
        </div>
      )}
      <Card className="mt-4">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-semibold">Jobs:</span>
          {["ingest", "forecast", "match", "alerts", "train"].map((j) => <Button key={j} variant="soft" className="!min-h-0 !py-1.5 !px-3 text-sm" onClick={() => run(j)}>{j}</Button>)}
          <span className="text-soil-500">{job}</span>
        </div>
      </Card>

      <div className="mt-6 flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold ${tab === t ? "bg-soil-900 text-white" : "bg-white"}`}>{t}</button>
        ))}
      </div>

      <div className="mt-4 overflow-x-auto rounded-3xl bg-white">
        {tab === "Matches" && (
          <Table head={["#", "Crop", "Qty", "₹/qtl", "Value", "Farmer", "Buyer", "km", "Score", "Status"]}
            rows={rows.map((m) => [m.id, `${m.emoji} ${m.crop} ${m.grade}`, m.quantity_qtl, inr(m.price_per_qtl), inr(m.value), m.farmer?.name, m.buyer?.name, Math.round(m.distance_km), m.score.toFixed(2), <Badge key="b" kind={m.status}>{m.status}</Badge>])} />
        )}
        {tab === "Transactions" && (
          <Table head={["#", "Crop", "Qty", "₹/qtl", "GMV", "Farmer fee", "Buyer fee", "Revenue", "When"]}
            rows={rows.map((t) => [t.id, t.crop, t.quantity_qtl, inr(t.price_per_qtl), inr(t.gross_amount), inr(t.farmer_commission), inr(t.buyer_commission), <b key="r">{inr(t.platform_revenue)}</b>, t.created_at.slice(0, 16).replace("T", " ")])} />
        )}
        {tab === "Users" && (
          <Table head={["#", "Phone", "Name", "Role", "Org / village", "Lang", "Joined"]}
            rows={rows.map((u) => [u.id, u.phone, u.name, <Badge key="r" kind={u.role === "admin" ? "accepted" : "info"}>{u.role}</Badge>, u.org, u.language, u.created_at.slice(0, 10)])} />
        )}
        {tab === "Data quality" && (
          <Table head={["#", "Source", "Status", "In", "Upserted", "Rejected", "Imputed", "Checks"]}
            rows={rows.map((r) => [r.id, r.source, r.status, r.rows_in, r.rows_upserted, r.rows_rejected, r.rows_imputed,
              <span key="d" className="text-xs text-soil-500">{Object.entries(r.details || {}).filter(([k, v]) => v && !["rows_in", "rows_clean"].includes(k)).map(([k, v]) => `${k}: ${v}`).join(", ") || "clean"}</span>])} />
        )}
        {tab === "Model" && report && (
          <div className="p-5">
            <p className="text-sm text-soil-500">
              Backtest: {report.meta.n_series} series · {report.meta.start} → {report.meta.end} · version {report.meta.version} · trained in {report.meta.train_seconds}s
            </p>
            <h3 className="mt-4 font-bold">MAPE by horizon (%) — lower is better</h3>
            <Table head={["Model", "7-day", "14-day", "30-day", "Mean"]}
              rows={Object.keys(report.mape_by_horizon).map((m) => [
                <span key="m" className={m === report.best_model ? "font-bold text-leaf-700" : ""}>{m}{m === report.best_model ? " ★ selected" : ""}</span>,
                ...["7", "14", "30"].map((h) => report.mape_by_horizon[m][h]?.toFixed(2)), report.mape_overall[m].toFixed(2)])} />
            <h3 className="mt-6 font-bold">By crop — {report.best_model}</h3>
            <Table head={["Crop", "MAPE %"]} rows={Object.entries(report.mape_by_crop[report.best_model] || {}).sort((a, b) => a[1] - b[1]).map(([c, v]) => [c, v.toFixed(2)])} />
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-soil-500"><tr>{head.map((h) => <th key={h} className="whitespace-nowrap p-3 font-medium">{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-soil-100">{r.map((c, j) => <td key={j} className="whitespace-nowrap p-3">{c}</td>)}</tr>)}</tbody>
    </table>
  );
}
