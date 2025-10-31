'use client';

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { login, startOAuth } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTarget = params.get("redirect") ?? "/";

  const supportsLocal = AUTH_MODE === "DEFAULT" || AUTH_MODE === "HYBRID";
  const supportsOAuth = AUTH_MODE === "HYBRID" || AUTH_MODE === "OAUTH";

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!supportsLocal) {
        return;
      }

      try {
        setIsSubmitting(true);
        setError(null);
        await login({ email, password, remember_me: rememberMe });
        router.push(redirectTarget || "/");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to sign in");
      } finally {
        setIsSubmitting(false);
      }
    },
    [email, password, rememberMe, redirectTarget, router, supportsLocal],
  );

  const handleOAuth = useCallback(async () => {
    try {
      setIsSubmitting(true);
      const redirectUri = `${window.location.origin}/auth/oauth/callback`;
      const { authorization_url } = await startOAuth(redirectUri);
      window.location.href = authorization_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start Microsoft login");
      setIsSubmitting(false);
    }
  }, []);

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
              Forgot your password? <Link href="/auth/forgot-password" className="font-semibold text-indigo-600 hover:text-indigo-500">Reset it</Link>
            </p>
            <p className="text-sm">Need access? {registerLink}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">This environment is configured for Microsoft sign-in only.</p>
        )
      }
    >
      {supportsLocal ? (
        <form className="space-y-4" onSubmit={handleSubmit}>
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
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            Remember this device
          </label>
          {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {isSubmitting ? "Verifying..." : "Sign in"}
          </button>
        </form>
      ) : error ? (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}

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
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-indigo-400 hover:text-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">MS</span>
            Continue with Microsoft 365
          </button>
        </div>
      ) : null}
    </AuthCard>
  );
}
