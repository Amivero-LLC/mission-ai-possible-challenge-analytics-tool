import LoginForm, { type LoginNotice } from "./LoginForm";

export const dynamic = "force-dynamic";

type PageSearchParams = Record<string, string | string[] | undefined>;

type LoginPageProps = {
  searchParams?: PageSearchParams;
};

function asString(value: string | string[] | undefined): string | undefined {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value[0];
  }
  return undefined;
}

function resolveNotice(params: PageSearchParams = {}): LoginNotice | null {
  const reason = asString(params.reason);
  const status = asString(params.status);

  if (reason === "expired") {
    return {
      tone: "warning",
      message: "Your session ended due to inactivity. Please sign in again to continue.",
    };
  }

  if (status === "logged_out") {
    return {
      tone: "success",
      message: "You have signed out securely.",
    };
  }

  return null;
}

export default function LoginPage({ searchParams = {} }: LoginPageProps) {
  const redirectParam = asString(searchParams.redirect);
  const notice = resolveNotice(searchParams);

  return <LoginForm redirectParam={redirectParam} initialNotice={notice} />;
}
