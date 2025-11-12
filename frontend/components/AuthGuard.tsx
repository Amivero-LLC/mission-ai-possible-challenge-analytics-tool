"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface AuthGuardProps {
  children: React.ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkAuth = () => {
      // Check if user has access token in localStorage
      const token = localStorage.getItem("maip_access_token");
      const expires = localStorage.getItem("maip_token_expires");

      if (!token || !expires) {
        // No token, redirect to login
        const currentPath = window.location.pathname + window.location.search;
        router.push(`/auth/login?redirect=${encodeURIComponent(currentPath)}`);
        return;
      }

      // Check if token is expired
      const expiresAt = parseInt(expires, 10);
      if (Date.now() >= expiresAt) {
        // Token expired, clear it and redirect to login
        localStorage.removeItem("maip_access_token");
        localStorage.removeItem("maip_token_expires");
        const currentPath = window.location.pathname + window.location.search;
        router.push(`/auth/login?redirect=${encodeURIComponent(currentPath)}`);
        return;
      }

      // Token exists and is valid
      setIsChecking(false);
    };

    checkAuth();
  }, [router]);

  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return <>{children}</>;
}
