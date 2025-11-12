"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import DashboardPage from "./DashboardPage";
import { fetchDashboard } from "../lib/api";
import type { DashboardResponse } from "../types/dashboard";

interface DashboardWrapperProps {
  initialData: DashboardResponse | null;
}

export default function DashboardWrapper({ initialData }: DashboardWrapperProps) {
  const router = useRouter();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardResponse | null>(initialData);
  const [isLoading, setIsLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Check if user has access token in localStorage
    const token = localStorage.getItem("maip_access_token");
    const expires = localStorage.getItem("maip_token_expires");

    if (!token || !expires) {
      // No token, redirect to login
      router.push("/auth/login?redirect=%2F");
      return;
    }

    // Check if token is expired
    const expiresAt = parseInt(expires, 10);
    if (Date.now() >= expiresAt) {
      // Token expired, clear it and redirect to login
      localStorage.removeItem("maip_access_token");
      localStorage.removeItem("maip_token_expires");
      router.push("/auth/login?redirect=%2F");
      return;
    }

    // Token exists and is valid
    setIsAuthorized(true);

    // If no initial data, fetch it client-side
    if (!initialData) {
      fetchDashboard()
        .then((data) => {
          setDashboardData(data);
          setIsLoading(false);
        })
        .catch((err) => {
          console.error("[DashboardWrapper] Failed to fetch dashboard:", err);
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
          setIsLoading(false);
        });
    }
  }, [router, initialData]);

  if (!isAuthorized || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">
          {!isAuthorized ? "Checking authorization..." : "Loading dashboard..."}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 mb-2">Failed to load dashboard</div>
          <div className="text-gray-600 text-sm">{error}</div>
          <button
            onClick={() => router.push("/auth/login")}
            className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">No dashboard data available</div>
      </div>
    );
  }

  return <DashboardPage initialData={dashboardData} />;
}
