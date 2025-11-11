'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { login, startOAuth } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

type BannerTone = "success" | "warning" | "error";

const toneClassMap: Record<BannerTone, string> = {
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  error: "border-red-200 bg-red-50 text-red-700",
};

export interface LoginNotice {
  tone: BannerTone;
  message: string;
}

interface LoginFormProps {
  redirectParam?: string;
  initialNotice?: LoginNotice | null;
}

export default function LoginForm({ redirectParam, initialNotice = null }: LoginFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [banner, setBanner] = useState<{ message: string; tone: BannerTone } | null>(null);
  const [notice, setNotice] = useState(initialNotice);

  useEffect(() => {
    setNotice(initialNotice ?? null);
  }, [initialNotice]);

  const redirectTarget = useMemo(() => {
    if (!redirectParam) {
      return "/";
    }
    try {
      const decoded = decodeURIComponent(redirectParam);
      if (!decoded.startsWith("/") || decoded.startsWith("/auth/")) {
        return "/";
      }
      return decoded || "/";
    } catch {
      return "/";
    }
  }, [redirectParam]);

  const supportsLocal = AUTH_MODE === "DEFAULT" || AUTH_MODE === "HYBRID";
  const supportsOAuth = AUTH_MODE === "HYBRID" || AUTH_MODE === "OAUTH";

  useEffect(() => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("maip_post_auth_redirect", redirectTarget || "/");
      if (sessionStorage.getItem("maip_auth_notice") === "logged_out") {
        sessionStorage.removeItem("maip_auth_notice");
      }
    }
  }, [redirectTarget]);

  useEffect(() => {
    if (!banner) {
      return undefined;
    }
    const timeout = window.setTimeout(() => setBanner(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [banner]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!supportsLocal || isSubmitting) {
        return;
      }

      try {
        setIsSubmitting(true);
        setBanner(null);
        if (typeof window !== "undefined") {
          sessionStorage.setItem("maip_post_auth_redirect", redirectTarget || "/");
        }
        await login({ email, password, remember_me: rememberMe });
        const storedTarget =
          (typeof window !== "undefined" ? sessionStorage.getItem("maip_post_auth_redirect") : null) ||
          redirectTarget ||
          "/";
        if (typeof window !== "undefined") {
          sessionStorage.setItem("maip_auth_notice", "signed_in");
          sessionStorage.removeItem("maip_post_auth_redirect");
        }
        router.replace(storedTarget || "/");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to sign in";
        setBanner({ message, tone: "error" });
        setIsSubmitting(false);
      }
    },
    [email, password, rememberMe, redirectTarget, router, supportsLocal, isSubmitting],
  );

  const handleOAuth = useCallback(async () => {
    if (isSubmitting) {
      return;
    }
    try {
      setIsSubmitting(true);
      setBanner(null);
      const redirectUri = `${window.location.origin}/auth/oauth/callback`;
      sessionStorage.setItem("maip_post_auth_redirect", redirectTarget || "/");
      const { authorization_url } = await startOAuth(redirectUri, redirectTarget || "/");
      window.location.href = authorization_url;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to start Microsoft login";
      setBanner({ message, tone: "error" });
      setIsSubmitting(false);
    }
  }, [redirectTarget, isSubmitting]);

  const registerLink = useMemo(() => {
    if (!supportsLocal) {
      return null;
    }
    return (
      <Link className="font-semibold text-indigo-600 hover:text-indigo-500" href="/auth/register">
        Create account
      </Link>
    );
  }, [supportsLocal]);

  return (
    <AuthCard
      title="Sign in to Mission:AI Possible"
      subtitle="Access mission telemetry, approve teammates, and manage secure analytics."
      footer={
        supportsLocal ? (
          <div className="space-y-1">
            <p className="text-sm">
              Forgot your password?{" "}
              <Link href="/auth/forgot-password" className="font-semibold text-indigo-600 hover:text-indigo-500">
                Reset it
              </Link>
            </p>
            <p className="text-sm">Need access? {registerLink}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">This environment is configured for Microsoft sign-in only.</p>
        )
      }
    >
      {notice ? (
        <div className={`rounded-lg border px-4 py-3 text-sm ${toneClassMap[notice.tone]}`}>
          {notice.message}
        </div>
      ) : null}
      {banner ? (
        <div className={`rounded-lg border px-4 py-3 text-sm ${toneClassMap[banner.tone]}`}>
          {banner.message}
        </div>
      ) : null}
      {supportsLocal ? (
        <form className="relative space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-1">
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              Work Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
              disabled={isSubmitting}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
              disabled={isSubmitting}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              disabled={isSubmitting}
            />
            Remember this device
          </label>
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-indigo-400"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <span className="auth-spinner" aria-hidden="true" />
                Signing in…
              </span>
            ) : (
              "Sign in"
            )}
          </button>
          {isSubmitting ? (
            <div className="auth-loading-overlay" aria-hidden="true">
              <div className="auth-loading-overlay__content">
                <span className="auth-spinner auth-spinner--lg" />
                <p className="text-sm font-medium text-slate-600">Verifying credentials…</p>
              </div>
            </div>
          ) : null}
        </form>
      ) : (
        <p className="text-sm text-slate-500">Microsoft sign-in is required for this workspace.</p>
      )}

      {supportsOAuth ? (
        <div className="space-y-3">
          {supportsLocal ? (
            <div className="relative flex items-center">
              <span className="flex-1 border-t border-slate-200" />
              <span className="px-3 text-xs uppercase tracking-wide text-slate-500">or</span>
              <span className="flex-1 border-t border-slate-200" />
            </div>
          ) : null}
          <button
            type="button"
            onClick={handleOAuth}
            disabled={isSubmitting}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-indigo-400 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
          >
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              MS
            </span>
            {isSubmitting ? "Redirecting…" : "Continue with Microsoft 365"}
          </button>
        </div>
      ) : null}
    </AuthCard>
  );
}
