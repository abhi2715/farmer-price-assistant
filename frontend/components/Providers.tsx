"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { outbox } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n";

const NetCtx = createContext({ online: true, pending: 0 });
export const useNet = () => useContext(NetCtx);

export default function Providers({ children }: { children: ReactNode }) {
  const [online, setOnline] = useState(true);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    const sync = async () => {
      await outbox.flush();
      setPending(outbox.list().length);
    };
    const up = () => {
      setOnline(true);
      sync();
    };
    const down = () => setOnline(false);
    setOnline(navigator.onLine);
    setPending(outbox.list().length);
    if (navigator.onLine) sync();
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    const iv = setInterval(() => setPending(outbox.list().length), 4000);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
      clearInterval(iv);
    };
  }, []);

  return (
    <I18nProvider>
      <NetCtx.Provider value={{ online, pending }}>{children}</NetCtx.Provider>
    </I18nProvider>
  );
}
