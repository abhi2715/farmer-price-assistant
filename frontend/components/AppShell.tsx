"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api, session, type User } from "@/lib/api";
import { LANGS, useI18n, type Lang } from "@/lib/i18n";
import { useNet } from "./Providers";

export function LangSwitch({ compact = false }: { compact?: boolean }) {
  const { lang, setLang } = useI18n();
  const change = (l: Lang) => {
    setLang(l);
    if (session.token()) api("/me", { method: "PATCH", body: { language: l } }).then(session.setUser).catch(() => {});
  };
  return (
    <div className="flex rounded-full bg-soil-100 p-0.5 text-sm" role="group" aria-label="Language">
      {LANGS.map((l) => (
        <button key={l.code} onClick={() => change(l.code)} aria-pressed={lang === l.code}
          className={`rounded-full px-2.5 py-1 ${lang === l.code ? "bg-white font-semibold shadow-sm" : "text-soil-500"}`}>
          {compact ? l.label.slice(0, 2) : l.label}
        </button>
      ))}
    </div>
  );
}

const FARMER_NAV = [
  { href: "/farmer/", key: "nav_sell", icon: "M3 12l9-8 9 8M5 10v10h14V10" },
  { href: "/farmer/forecast/", key: "nav_prices", icon: "M3 17l6-6 4 4 8-8M15 7h6v6" },
  { href: "/farmer/lots/", key: "nav_lots", icon: "M4 7h16M4 12h16M4 17h10" },
  { href: "/farmer/alerts/", key: "nav_alerts", icon: "M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2a2 2 0 01-.6 1.4L4 17h5m6 0a3 3 0 11-6 0" },
];

/** Auth + role guard, header, offline banner and (for farmers) a thumb-friendly bottom nav. */
export default function AppShell({ role, children, title }: { role: User["role"]; children: ReactNode; title?: string }) {
  const router = useRouter();
  const path = usePathname();
  const { t, lang, setLang } = useI18n();
  const { online, pending } = useNet();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const u = session.user();
    if (!session.token() || !u) {
      router.replace("/login/");
      return;
    }
    if (u.role !== role) {
      router.replace(u.role === "farmer" ? "/farmer/" : `/${u.role}/`);
      return;
    }
    setUser(u);
    try {
      if (!localStorage.getItem("lang")) setLang(u.language);
    } catch {}
  }, [role, router, setLang]);

  if (!user) return null;
  const logout = () => {
    session.clear();
    router.replace("/login/");
  };

  return (
    <div className="min-h-dvh bg-soil-50 pb-24">
      <header className="sticky top-0 z-20 border-b border-soil-100 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-2 px-4 py-3">
          <Link href={role === "farmer" ? "/farmer/" : `/${role}/`} className="flex items-center gap-2 font-bold tracking-tight">
            <img src="/icons/icon.svg" alt="" width={28} height={28} />
            <span>{title || "AgriRoute"}</span>
          </Link>
          <div className="flex items-center gap-2">
            <LangSwitch compact />
            <button onClick={logout} className="rounded-full px-2 py-1 text-sm text-soil-500" title={t("logout")}>
              ⎋
            </button>
          </div>
        </div>
        {(!online || pending > 0) && (
          <div className="bg-amber-50 px-4 py-1.5 text-center text-sm text-amber-800">
            {!online && t("offline")} {pending > 0 && `· ${t("pending_sync", { n: pending })}`}
          </div>
        )}
      </header>
      <main className="mx-auto max-w-3xl px-4 pt-4" lang={lang}>{children}</main>
      {role === "farmer" && (
        <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-soil-100 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
          <div className="mx-auto grid max-w-3xl grid-cols-4">
            {FARMER_NAV.map((n) => {
              const active = path === n.href;
              return (
                <Link key={n.href} href={n.href} className={`flex flex-col items-center gap-0.5 py-2.5 text-xs ${active ? "text-leaf-700 font-semibold" : "text-soil-500"}`}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                    <path d={n.icon} />
                  </svg>
                  {t(n.key)}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}
