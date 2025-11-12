'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { AuthRequestError, completeRegistration, login, startRegistration } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [step, setStep] = useState<"email" | "password">("email");
  const [emailNeedingPassword, setEmailNeedingPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  if (AUTH_MODE === "OAUTH") {
    return (
      <AuthCard title="Registration disabled" subtitle="This environment requires Microsoft 365 login." footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Return to sign in</Link>}>
        <p className="text-sm text-slate-600">Contact your administrator to be added to the approved users list.</p>
      </AuthCard>
    );
  }

  async function handleEmailSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setIsSubmitting(true);
      setError(null);
      setInfo(null);
      const result = await startRegistration({ email });
      setInfo(result.message);

      if (result.status === "pending_approval") {
        setEmail("");
        return;
      }

      if (result.status === "password_reset_required") {
        router.push("/auth/forgot-password");
        return;
      }

      setPassword("");
      setConfirmPassword("");
      setEmailNeedingPassword(email);
      setStep("password");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to continue");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePasswordSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      setInfo(null);
      await completeRegistration({ email: emailNeedingPassword, password });
      const tokenPair = await login({ email: emailNeedingPassword, password });

      if (typeof window !== "undefined") {
        localStorage.setItem("maip_access_token", tokenPair.access_token);
        localStorage.setItem("maip_token_expires", String(Date.now() + tokenPair.expires_in * 1000));
        sessionStorage.setItem("maip_auth_notice", "signed_in");
        const target = sessionStorage.getItem("maip_post_auth_redirect") || "/";
        sessionStorage.removeItem("maip_post_auth_redirect");
        window.location.href = target || "/";
        return;
      }

      router.push("/");
      router.refresh();
    } catch (err) {
      if (err instanceof AuthRequestError && err.status === 403) {
        setStep("email");
        setEmail("");
        setEmailNeedingPassword("");
        setPassword("");
        setConfirmPassword("");
        setInfo("Approval is still pending. We'll email you once it's ready.");
        return;
      }
      const message = err instanceof Error ? err.message : "Unable to set password";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Request access"
      subtitle="Start with your work email. We'll guide you through the next steps."
      footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Already have access? Sign in</Link>}
    >
      {step === "email" ? (
        <form className="space-y-4" onSubmit={handleEmailSubmit}>
          <div className="space-y-1">
            <label className="block text-sm font-medium text-slate-700" htmlFor="email">
              Work Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
              autoComplete="email"
            />
          </div>
          {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
          {info ? <p className="text-sm text-emerald-600" role="status">{info}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {isSubmitting ? "Checking..." : "Continue"}
          </button>
        </form>
      ) : (
        <form className="space-y-4" onSubmit={handlePasswordSubmit}>
          <div className="space-y-2">
            <p className="text-sm text-slate-600">Set a password for <span className="font-semibold text-slate-900">{emailNeedingPassword}</span>.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="block text-sm font-medium text-slate-700" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                minLength={12}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-sm font-medium text-slate-700" htmlFor="confirmPassword">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                minLength={12}
                required
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
                autoComplete="new-password"
              />
            </div>
          </div>
          {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
          {info ? <p className="text-sm text-emerald-600" role="status">{info}</p> : null}
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            {isSubmitting ? "Saving..." : "Set password"}
          </button>
        </form>
      )}
      <p className="text-xs text-slate-500">
        Your email must be pre-provisioned by administrators. Accounts remain locked until approved.
      </p>
    </AuthCard>
  );
}
