import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PUBLIC_PATHS = new Set([
  "/auth/login",
  "/auth/register",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/oauth/callback",
  "/setup",
  "/status/health",
]);

const API_PREFIXES = ["/api", "/_next", "/static", "/favicon.ico", "/manifest.json", "/apple-icon.png", "/icon.svg"];
const SESSION_COOKIE = "maip_session";

function isPublicPath(pathname: string): boolean {
  if (pathname === "/") {
    return false;
  }
  if (PUBLIC_PATHS.has(pathname)) {
    return true;
  }
  for (const base of Array.from(PUBLIC_PATHS)) {
    if (pathname.startsWith(`${base}/`)) {
      return true;
    }
  }
  return false;
}

function isBypassed(pathname: string): boolean {
  return API_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function resolveApiBase(): string {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000"
  );
}

async function fetchSetupStatus(request: NextRequest): Promise<boolean | null> {
  try {
    const baseUrl = resolveApiBase();
    console.log(`[Middleware] Checking setup status at: ${baseUrl}/api/setup/status`);
    const response = await fetch(new URL("/api/setup/status", baseUrl), {
      headers: {
        cookie: request.headers.get("cookie") ?? "",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(10000), // 10 second timeout for Railway internal networking
    });
    if (!response.ok) {
      console.error(`[Middleware] Setup status check failed: ${response.status} ${response.statusText}`);
      return null; // Unable to determine
    }
    const payload = (await response.json()) as { needs_setup?: boolean };
    console.log(`[Middleware] Setup status response:`, payload);
    return Boolean(payload?.needs_setup);
  } catch (error) {
    console.error("[Middleware] Failed to fetch setup status from backend:", error);
    return null; // Unable to determine
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isBypassed(pathname)) {
    return NextResponse.next();
  }

  const needsSetup = await fetchSetupStatus(request);

  // If we can't determine setup status (null), allow access to setup and login pages
  // but redirect home to setup by default for safety
  if (needsSetup === null) {
    console.log("[Middleware] Unable to determine setup status, allowing setup and login pages");
    if (pathname === "/" || (!pathname.startsWith("/setup") && !pathname.startsWith("/auth"))) {
      return NextResponse.redirect(new URL("/setup", request.url));
    }
    return NextResponse.next();
  }

  if (needsSetup) {
    if (!pathname.startsWith("/setup")) {
      return NextResponse.redirect(new URL("/setup", request.url));
    }
    return NextResponse.next();
  }

  if (pathname.startsWith("/setup")) {
    return NextResponse.redirect(new URL("/auth/login", request.url));
  }

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  if (!request.cookies.has(SESSION_COOKIE)) {
    const loginUrl = new URL("/auth/login", request.url);
    const redirectTarget = `${pathname}${request.nextUrl.search}`.replace(/\?$/, "");
    if (redirectTarget && redirectTarget !== "/auth/login") {
      loginUrl.searchParams.set("redirect", redirectTarget);
    }
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/:path*",
};
