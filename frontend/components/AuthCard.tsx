'use client';

import Link from "next/link";
import { ReactNode } from "react";

interface AuthCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

export default function AuthCard({ title, subtitle, children, footer }: AuthCardProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-100 px-4 py-12 dark:bg-slate-950">
      <div className="w-full max-w-md space-y-6 rounded-xl bg-white p-6 shadow-lg ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-800">
        <header className="space-y-2 text-center">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">{title}</h1>
          {subtitle ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">{subtitle}</p>
          ) : null}
        </header>
        <div className="space-y-4">{children}</div>
        {footer ? <div className="border-t border-slate-100 pt-4 text-center text-sm text-slate-600 dark:border-slate-800 dark:text-slate-300">{footer}</div> : null}
      </div>
      <p className="mt-8 text-center text-xs text-slate-500 dark:text-slate-400">
        <Link href="/">Mission:AI Possible</Link> &bull; Secure Access Portal
      </p>
    </div>
  );
}
