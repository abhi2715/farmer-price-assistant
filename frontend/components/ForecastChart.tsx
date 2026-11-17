"use client";
// Dependency-free SVG chart: history line, forecast line and 80% interval band.
type Pt = { date: string; value: number };
type F = { date: string; yhat: number; lo: number; hi: number };

export default function ForecastChart({ history, forecast, height = 220 }: { history: Pt[]; forecast: F[]; height?: number }) {
  const W = 640, H = height, PL = 48, PR = 12, PT = 12, PB = 26;
  if (!history.length && !forecast.length) return null;
  const all = [...history.map((h) => h.date), ...forecast.map((f) => f.date)];
  const t0 = Date.parse(all[0]), t1 = Date.parse(all[all.length - 1]);
  const vals = [...history.map((h) => h.value), ...forecast.flatMap((f) => [f.lo, f.hi])];
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || hi * 0.05;
  lo -= pad;
  hi += pad;
  const x = (d: string) => PL + ((Date.parse(d) - t0) / Math.max(1, t1 - t0)) * (W - PL - PR);
  const y = (v: number) => PT + (1 - (v - lo) / (hi - lo)) * (H - PT - PB);
  const line = (pts: [number, number][]) => pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("");
  const last = history[history.length - 1];
  const fc = last ? [{ date: last.date, yhat: last.value, lo: last.value, hi: last.value }, ...forecast] : forecast;
  const band = line(fc.map((f) => [x(f.date), y(f.hi)])) + fc.slice().reverse().map((f) => `L${x(f.date).toFixed(1)},${y(f.lo).toFixed(1)}`).join("") + "Z";
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  const fmt = (d: string) => new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Price history and forecast">
      {ticks.map((v) => (
        <g key={v}>
          <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="#e7e5e4" strokeDasharray="3 4" />
          <text x={PL - 6} y={y(v) + 4} textAnchor="end" fontSize="11" fill="#78716c">₹{Math.round(v).toLocaleString("en-IN")}</text>
        </g>
      ))}
      <path d={band} fill="#22c55e" opacity="0.14" />
      {history.length > 1 && <path d={line(history.map((h) => [x(h.date), y(h.value)]))} fill="none" stroke="#44403c" strokeWidth="2" />}
      <path d={line(fc.map((f) => [x(f.date), y(f.yhat)]))} fill="none" stroke="#16a34a" strokeWidth="2.5" strokeDasharray="6 4" />
      {last && <circle cx={x(last.date)} cy={y(last.value)} r="4" fill="#1c1917" />}
      {last && <line x1={x(last.date)} x2={x(last.date)} y1={PT} y2={H - PB} stroke="#a8a29e" strokeDasharray="2 3" />}
      <text x={PL} y={H - 6} fontSize="11" fill="#78716c">{fmt(all[0])}</text>
      {last && <text x={x(last.date)} y={H - 6} fontSize="11" fill="#1c1917" textAnchor="middle">{fmt(last.date)}</text>}
      <text x={W - PR} y={H - 6} fontSize="11" fill="#78716c" textAnchor="end">{fmt(all[all.length - 1])}</text>
    </svg>
  );
}
