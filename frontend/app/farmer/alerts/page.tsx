"use client";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { Badge, Card, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { canSpeak, speak } from "@/lib/voice";

type A = { id: number; kind: string; severity: string; text: string; is_read: boolean; channels: string[]; created_at: string };
const ICON: Record<string, string> = { forecast_rise: "📈", forecast_drop: "📉", price_rise: "⬆️", price_drop: "⬇️", match: "🤝", deal: "✅" };

export default function Alerts() {
  const { t, lang } = useI18n();
  const [items, setItems] = useState<A[] | null>(null);
  const load = useCallback(() => api<A[]>(`/alerts?lang=${lang}`).then(setItems).catch(() => setItems([])), [lang]);
  useEffect(() => {
    load();
  }, [load]);

  const readAll = async () => {
    await api("/alerts/read-all", { method: "POST" }).catch(() => {});
    load();
  };

  return (
    <AppShell role="farmer">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("nav_alerts")}</h1>
        {!!items?.some((a) => !a.is_read) && <button onClick={readAll} className="text-sm text-leaf-700">{t("mark_all_read")}</button>}
      </div>
      {items === null && <Spinner />}
      {items?.length === 0 && <p className="mt-4 text-soil-500">{t("no_alerts")}</p>}
      <div className="mt-4 flex flex-col gap-3">
        {items?.map((a) => (
          <Card key={a.id} className={a.is_read ? "opacity-70" : "ring-1 ring-leaf-500/30"}>
            <div className="flex gap-3">
              <span className="text-2xl" aria-hidden>{ICON[a.kind] || "🔔"}</span>
              <div className="flex-1">
                <p className="leading-snug">{a.text}</p>
                <div className="mt-2 flex items-center gap-2 text-xs text-soil-400">
                  <span>{new Date(a.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</span>
                  {a.channels.filter((c) => c !== "in_app").map((c) => <Badge key={c} kind="info">{c}</Badge>)}
                </div>
              </div>
              {canSpeak() && <button onClick={() => speak(a.text, lang)} aria-label={t("listen")} className="self-start text-xl">🔊</button>}
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
