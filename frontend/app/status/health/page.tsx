"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

interface BackendStatus {
  status: "checking" | "ok" | "error";
  message?: string;
  apiUrl: string;
  responseTime?: number;
  timestamp?: string;
}

function HealthPage() {
  const [mounted, setMounted] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [frontendOrigin, setFrontendOrigin] = useState("");
  const [backend, setBackend] = useState<BackendStatus>({
    status: "checking",
    apiUrl: "",
  });

  useEffect(() => {
    setMounted(true);
    setCurrentTime(new Date().toISOString());
    setFrontendOrigin(window.location.origin);

    const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    setBackend((prev) => ({ ...prev, apiUrl }));

    checkBackendHealth(apiUrl);
  }, []);

  const checkBackendHealth = async (apiUrl: string) => {
    const startTime = Date.now();

    try {
      const response = await fetch(`${apiUrl}/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });

      const responseTime = Date.now() - startTime;

      if (response.ok) {
        const data = await response.json();
        setBackend({
          status: "ok",
          message: data.status || "Backend is healthy",
          apiUrl,
          responseTime,
          timestamp: new Date().toISOString(),
        });
      } else {
        setBackend({
          status: "error",
          message: `HTTP ${response.status}: ${response.statusText}`,
          apiUrl,
          responseTime,
          timestamp: new Date().toISOString(),
        });
      }
    } catch (error) {
      const responseTime = Date.now() - startTime;
      setBackend({
        status: "error",
        message: error instanceof Error ? error.message : "Failed to connect to backend",
        apiUrl,
        responseTime,
        timestamp: new Date().toISOString(),
      });
    }
  };

  const handleRefresh = () => {
    setBackend((prev) => ({ ...prev, status: "checking" }));
    checkBackendHealth(backend.apiUrl);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ok":
        return "text-green-600 bg-green-100";
      case "error":
        return "text-red-600 bg-red-100";
      case "checking":
        return "text-yellow-600 bg-yellow-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ok":
        return "✓";
      case "error":
        return "✗";
      case "checking":
        return "⟳";
      default:
        return "?";
    }
  };

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 flex items-center justify-center">
        <div className="text-gray-600">Loading health status...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white shadow-md rounded-lg p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">System Health Status</h1>
          <p className="text-gray-600 mb-8">
            Public health check endpoint - No authentication required
          </p>

          {/* Frontend Health */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <span className="mr-2">Frontend Service</span>
              <span className="px-3 py-1 rounded-full text-sm font-medium text-green-600 bg-green-100">
                ✓ OK
              </span>
            </h2>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Environment:</span>
                <span className="font-mono text-sm">{process.env.NODE_ENV || "development"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Timestamp:</span>
                <span className="font-mono text-sm">{currentTime}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Page Status:</span>
                <span className="font-mono text-sm text-green-600">Hydrated Successfully</span>
              </div>
            </div>
          </div>

          {/* Backend Health */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
              <span className="mr-2">Backend Service</span>
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(backend.status)}`}>
                {getStatusIcon(backend.status)} {backend.status.toUpperCase()}
              </span>
            </h2>
            <div className="bg-gray-50 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">API URL:</span>
                <span className="font-mono text-sm break-all">{backend.apiUrl}</span>
              </div>
              {backend.responseTime !== undefined && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Response Time:</span>
                  <span className="font-mono text-sm">{backend.responseTime}ms</span>
                </div>
              )}
              {backend.message && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Message:</span>
                  <span className="font-mono text-sm">{backend.message}</span>
                </div>
              )}
              {backend.timestamp && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Timestamp:</span>
                  <span className="font-mono text-sm">{backend.timestamp}</span>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-4">
            <button
              onClick={handleRefresh}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Refresh Backend Status
            </button>
            <Link
              href="/"
              className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors inline-block text-center"
            >
              Back to Dashboard
            </Link>
          </div>

          {/* Debug Information */}
          <div className="mt-8 pt-8 border-t border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Troubleshooting Information</h3>
            <div className="bg-gray-50 rounded-lg p-4 space-y-4">
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Backend Connection Issues?</h4>
                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                  <li>Verify the backend service is running</li>
                  <li>Check CORS configuration allows your frontend origin</li>
                  <li>Ensure firewall rules permit traffic between services</li>
                  <li>For Railway: Use http://&lt;service-name&gt;.railway.internal for internal calls</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">CORS Configuration</h4>
                <div className="text-sm text-gray-600 space-y-2">
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                    <p className="font-semibold text-yellow-800 mb-1">⚠️ IMPORTANT FOR RAILWAY:</p>
                    <p className="mb-2">Your backend needs to allow requests from this frontend origin:</p>
                    <p className="font-mono text-xs bg-white p-2 rounded border break-all">
                      {frontendOrigin}
                    </p>
                    <p className="mt-2 text-xs">
                      Add this to your Railway <strong>backend service</strong> environment variables:
                    </p>
                    <p className="font-mono text-xs bg-white p-2 rounded border mt-1 break-all">
                      CORS_ALLOW_ORIGINS={frontendOrigin}
                    </p>
                  </div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 mb-2">Environment Variables</h4>
                <div className="text-sm text-gray-600">
                  <p>
                    <span className="font-mono">NEXT_PUBLIC_API_BASE_URL</span> is used for browser-side API calls
                  </p>
                  <p className="mt-1">
                    Current value: <span className="font-mono">{backend.apiUrl}</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 text-center text-sm text-gray-500">
          <p>This is a public health check endpoint accessible without authentication</p>
        </div>
      </div>
    </div>
  );
}

export default HealthPage;
