'use client';

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import AuthCard from "../../../../components/AuthCard";
import { completeOAuth } from "../../../../lib/auth";

interface OAuthCallbackClientProps {
  code?: string;
  state?: string;
}

export default function OAuthCallbackClient({ code, state }: OAuthCallbackClientProps) {
  const router = useRouter();
  const [statusMessage, setStatusMessage] = useState("Completing Microsoft login...");
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!code || !state) {
      setStatusMessage("Missing authorization details. Restart the sign-in flow.");
      setIsError(true);
      return;
    }

    let active = true;

    async function finalize(authCode: string, authState: string) {
      try {
        await completeOAuth({
          code: authCode,
          state: authState,
          redirect_uri: `${window.location.origin}/auth/oauth/callback`,
        });
        const target =
          (typeof window !== "undefined" ? sessionStorage.getItem("maip_post_auth_redirect") : null) || "/";
        if (typeof window !== "undefined") {
          sessionStorage.setItem("maip_auth_notice", "signed_in");
          sessionStorage.removeItem("maip_post_auth_redirect");
        }
        if (!active) {
          return;
        }
        router.replace(target || "/");
      } catch (err) {
        if (!active) {
          return;
        }
        const message = err instanceof Error ? err.message : "Unable to complete sign in";
        setStatusMessage(message);
        setIsError(true);
      }
    }

    finalize(code, state);

    return () => {
      active = false;
    };
  }, [code, state, router]);

  return (
    <AuthCard
      title="Microsoft login"
      subtitle="Securely verifying your identity with Microsoft Entra ID."
      footer={
        <Link href="/auth/login" className="font-semibold text-indigo-600 hover:text-indigo-500">
          Back to sign in
        </Link>
      }
    >
      <div className={`rounded-lg border px-4 py-3 text-sm ${isError ? "border-red-200 bg-red-50 text-red-700" : "border-indigo-200 bg-indigo-50 text-indigo-700"}`}>
        {statusMessage}
      </div>
    </AuthCard>
  );
}
