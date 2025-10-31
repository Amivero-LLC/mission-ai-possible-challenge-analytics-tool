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
  for (const base of PUBLIC_PATHS) {
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

async function fetchSetupStatus(request: NextRequest): Promise<boolean> {
  try {
    const baseUrl = resolveApiBase();
    const response = await fetch(new URL("/api/setup/status", baseUrl), {
      headers: {
        cookie: request.headers.get("cookie") ?? "",
      },
      cache: "no-store",
    });
    if (!response.ok) {
      return false;
    }
    const payload = (await response.json()) as { needs_setup?: boolean };
    return Boolean(payload?.needs_setup);
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isBypassed(pathname)) {
    return NextResponse.next();
  }

  const needsSetup = await fetchSetupStatus(request);

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
