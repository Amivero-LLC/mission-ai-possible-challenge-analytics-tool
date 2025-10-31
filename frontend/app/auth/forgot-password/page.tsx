'use client';

import Link from "next/link";
import { useState } from "react";

import AuthCard from "../../../components/AuthCard";
import { forgotPassword } from "../../../lib/auth";

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "DEFAULT";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (AUTH_MODE === "OAUTH") {
    return (
      <AuthCard title="Password reset disabled" subtitle="Microsoft 365 manages authentication for this deployment." footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Return to sign in</Link>}>
        <p className="text-sm text-slate-600">Contact the administrator if you cannot access your Microsoft account.</p>
      </AuthCard>
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setIsSubmitting(true);
      setMessage(null);
      setError(null);
      await forgotPassword({ email });
      setMessage("If the email is registered, reset instructions are on their way.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthCard
      title="Reset your password"
      subtitle="Request a secure link to set a new password."
      footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Return to sign in</Link>}
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
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50"
          />
        </div>
        {error ? <p className="text-sm text-red-600" role="alert">{error}</p> : null}
        {message ? <p className="text-sm text-emerald-600" role="status">{message}</p> : null}
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex w-full items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          {isSubmitting ? "Sending..." : "Send reset link"}
        </button>
      </form>
      <p className="text-xs text-slate-500">Reset links expire after one hour for security.</p>
    </AuthCard>
  );
}
