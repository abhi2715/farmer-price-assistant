"use client";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({ variant = "primary", className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "soft" }) {
  const v = {
    primary: "bg-leaf-600 text-white active:bg-leaf-700 disabled:bg-soil-400",
    ghost: "bg-transparent text-soil-700 border border-soil-400/40 active:bg-soil-100",
    danger: "bg-white text-red-600 border border-red-200 active:bg-red-50",
    soft: "bg-leaf-50 text-leaf-700 active:bg-leaf-100",
  }[variant];
  return <button {...p} className={`rounded-2xl px-5 py-3.5 text-base font-semibold transition-colors min-h-[48px] ${v} ${className}`} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-3xl bg-white p-5 shadow-[0_1px_2px_rgba(0,0,0,.04),0_8px_24px_rgba(0,0,0,.04)] ${className}`}>{children}</div>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-soil-500" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-leaf-500 border-t-transparent" />
      {label}
    </div>
  );
}

const BADGE: Record<string, string> = {
  open: "bg-blue-50 text-blue-700", partially_matched: "bg-amber-50 text-amber-700", matched: "bg-leaf-50 text-leaf-700",
  sold: "bg-leaf-600 text-white", cancelled: "bg-soil-100 text-soil-500", proposed: "bg-amber-50 text-amber-700",
  accepted: "bg-leaf-600 text-white", rejected: "bg-soil-100 text-soil-500", warning: "bg-amber-50 text-amber-700",
  info: "bg-blue-50 text-blue-700",
};
export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE[kind] || "bg-soil-100 text-soil-700"}`}>{children}</span>;
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <Card>
      <div className="text-sm text-soil-500">{label}</div>
      <div className="mt-1 text-3xl font-bold tracking-tight">{value}</div>
      {sub && <div className="mt-1 text-xs text-soil-500">{sub}</div>}
    </Card>
  );
}
