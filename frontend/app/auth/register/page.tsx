'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { register as registerAccount } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      setInfo(null);
      await registerAccount({ email, username: username || undefined, password });
      setInfo("Registration submitted. Administrators will approve your account shortly.");
      setEmail("");
      setUsername("");
      setPassword("");
      setConfirmPassword("");
      setTimeout(() => router.push("/auth/login"), 4000);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unable to register";
      if (message.toLowerCase().includes("approval")) {
        setInfo(message);
        setTimeout(() => router.push("/auth/login"), 4000);
      } else {
        setError(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Request access"
      subtitle="Submit your work email to be approved by a Mission:AI Possible administrator."
      footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Already have access? Sign in</Link>}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
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
        <div className="space-y-1">
          <label className="block text-sm font-medium text-slate-700" htmlFor="username">
            Display Name (optional)
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
          />
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
          {isSubmitting ? "Submitting..." : "Submit for approval"}
        </button>
      </form>
      <p className="text-xs text-slate-500">
        Your email must be pre-provisioned by administrators. Accounts remain locked until approved.
      </p>
    </AuthCard>
  );
}
