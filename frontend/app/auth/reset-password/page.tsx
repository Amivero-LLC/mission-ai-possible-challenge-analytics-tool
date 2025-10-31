'use client';

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { resetPassword as resetPasswordRequest } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

export default function ResetPasswordPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setToken(params.get("token"));
  }, [params]);

  if (AUTH_MODE === "OAUTH") {
    return (
      <AuthCard title="Password reset disabled" subtitle="Microsoft 365 manages authentication for this deployment." footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Return to sign in</Link>}>
        <p className="text-sm text-slate-600">Contact the administrator if you cannot access your Microsoft account.</p>
      </AuthCard>
    );
  }

  if (!token) {
    return (
      <AuthCard title="Reset link missing" subtitle="Follow the link from your email to reset your password." footer={<Link href="/auth/forgot-password" className="font-semibold text-indigo-600 hover:text-indigo-500">Request a new link</Link>}>
        <p className="text-sm text-slate-600">Reset tokens expire quickly and can only be used once.</p>
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
      await resetPasswordRequest({ token, password });
      setMessage("Your password has been updated. Redirecting to sign in...");
      setTimeout(() => router.push("/auth/login"), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset password");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Choose a new password"
      subtitle="Passwords must be at least 12 characters and unique to this system."
      footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Return to sign in</Link>}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-1">
          <label className="block text-sm font-medium text-slate-700" htmlFor="password">
            New password
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
            Confirm password
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
        {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
        {message ? <p className="text-sm text-emerald-600" role="status">{message}</p> : null}
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          {isSubmitting ? "Saving..." : "Update password"}
        </button>
      </form>
      <p className="text-xs text-slate-500">This link becomes invalid once used or after expiry.</p>
    </AuthCard>
  );
}
