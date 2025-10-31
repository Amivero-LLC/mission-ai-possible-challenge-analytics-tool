'use client';

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import AuthCard from "../../../../components/AuthCard";
import { completeOAuth } from "../../../../lib/auth";

export default function OAuthCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [statusMessage, setStatusMessage] = useState("Completing Microsoft login...");
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");

    if (!code || !state) {
      setStatusMessage("Missing authorization details. Restart the sign-in flow.");
      setIsError(true);
      return;
    }

    async function finalize() {
      try {
        await completeOAuth({ code, state, redirect_uri: `${window.location.origin}/auth/oauth/callback` });
        const target =
          (typeof window !== "undefined" ? sessionStorage.getItem("maip_post_auth_redirect") : null) || "/";
        if (typeof window !== "undefined") {
          sessionStorage.setItem("maip_auth_notice", "signed_in");
          sessionStorage.removeItem("maip_post_auth_redirect");
        }
        router.replace(target || "/");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to complete sign in";
        setStatusMessage(message);
        setIsError(true);
      }
    }

    finalize();
  }, [router, params]);

  return (
    <AuthCard
      title="Microsoft login"
      subtitle="Securely verifying your identity with Microsoft Entra ID."
      footer={<Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">Back to sign in</Link>}
    >
      <div className={`rounded-lg border px-4 py-3 text-sm ${isError ? "border-red-200 bg-red-50 text-red-700" : "border-indigo-200 bg-indigo-50 text-indigo-700"}`}>
        {statusMessage}
      </div>
    </AuthCard>
  );
}
