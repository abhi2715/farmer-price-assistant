"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LangSwitch } from "@/components/AppShell";
import { Button, Card } from "@/components/ui";
import { ApiError, api, session, type User } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const DEMO = [
  { phone: "9000000001", label: "Farmer · Ramesh (Kolar)" },
  { phone: "9100000001", label: "Buyer · Anil Fresh Traders" },
  { phone: "9999999999", label: "Admin" },
];

export default function Login() {
  const { t, lang, setLang } = useI18n();
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [role, setRole] = useState<"farmer" | "buyer">("farmer");
  const [name, setName] = useState("");
  const [step, setStep] = useState<"phone" | "otp">("phone");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    const r = new URLSearchParams(location.search).get("role");
    if (r === "buyer" || r === "farmer") setRole(r);
    const u = session.user();
    if (session.token() && u) router.replace(u.role === "farmer" ? "/farmer/" : `/${u.role}/`);
  }, [router]);

  const request = async (p = phone) => {
    setErr("");
    if (!/^[6-9]\d{9}$/.test(p)) return setErr(t("phone") + " ✗");
    setBusy(true);
    try {
      const r = await api<{ dev_otp?: string }>("/auth/otp/request", { method: "POST", body: { phone: p } });
      setDevOtp(r.dev_otp || null);
      if (r.dev_otp) setOtp(r.dev_otp);
      setStep("otp");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setErr("");
    try {
      const r = await api<{ access_token: string; user: User; created: boolean }>("/auth/otp/verify", {
        method: "POST", body: { phone, otp, role, name, language: lang },
      });
      session.save(r.access_token, r.user);
      setLang(r.user.language);
      // New users: share location once so distances are real (optional).
      if (r.created && "geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
          (p) => api("/me", { method: "PATCH", body: { lat: +p.coords.latitude.toFixed(4), lon: +p.coords.longitude.toFixed(4) } })
            .then(session.setUser).catch(() => {}),
          () => {}, { timeout: 8000 },
        );
      }
      router.replace(r.user.role === "farmer" ? "/farmer/" : `/${r.user.role}/`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-dvh flex-col bg-soil-50">
      <div className="flex items-center justify-between px-5 py-4">
        <Link href="/" className="flex items-center gap-2 font-bold"><img src="/icons/icon.svg" alt="" width={28} height={28} /> AgriRoute</Link>
        <LangSwitch />
      </div>
      <div className="mx-auto w-full max-w-md flex-1 px-5 pt-6">
        <h1 className="animate-rise text-4xl font-bold tracking-tight">{t("login")}</h1>
        <Card className="mt-6 animate-rise">
          {step === "phone" ? (
            <form onSubmit={(e) => { e.preventDefault(); request(); }} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="phone">{t("phone")}</label>
                <div className="flex items-center gap-2">
                  <span className="rounded-2xl bg-soil-100 px-3 py-3 text-soil-500">+91</span>
                  <input id="phone" inputMode="numeric" autoComplete="tel-national" maxLength={10} value={phone}
                    onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))} className="flex-1 text-lg tracking-wider" placeholder="98xxxxxxxx" />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label>{t("i_am")}</label>
                <div className="grid grid-cols-2 gap-2">
                  {(["farmer", "buyer"] as const).map((r) => (
                    <button type="button" key={r} onClick={() => setRole(r)} aria-pressed={role === r}
                      className={`rounded-2xl border py-3 font-semibold ${role === r ? "border-leaf-600 bg-leaf-50 text-leaf-700" : "border-soil-400/40"}`}>
                      {r === "farmer" ? "🧑‍🌾 " : "🏪 "}{t(`role_${r}`)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="name">{t("your_name")}</label>
                <input id="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
              </div>
              <Button disabled={busy}>{t("send_otp")}</Button>
            </form>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); verify(); }} className="flex flex-col gap-4">
              <label htmlFor="otp">{t("otp")}</label>
              <input id="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} className="text-center text-2xl tracking-[0.5em]" autoFocus />
              {devOtp && <p className="text-center text-sm text-soil-500">{t("dev_otp", { otp: devOtp })}</p>}
              <Button disabled={busy || otp.length !== 6}>{t("verify")}</Button>
              <button type="button" onClick={() => setStep("phone")} className="text-sm text-soil-500">← {t("phone")}</button>
            </form>
          )}
          {err && <p className="mt-3 text-center text-sm text-red-600" role="alert">{err}</p>}
        </Card>
        <div className="mt-8">
          <p className="text-sm font-semibold text-soil-500">{t("demo_accounts")}</p>
          <div className="mt-2 flex flex-col gap-2">
            {DEMO.map((d) => (
              <button key={d.phone} onClick={() => { setPhone(d.phone); request(d.phone); }}
                className="flex items-center justify-between rounded-2xl bg-white px-4 py-3 text-left text-sm shadow-sm">
                <span>{d.label}</span>
                <span className="font-mono text-soil-500">{d.phone}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
