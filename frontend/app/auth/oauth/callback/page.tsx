import OAuthCallbackClient from "./OAuthCallbackClient";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

type OAuthCallbackPageProps = {
  searchParams?: SearchParams;
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

export default function OAuthCallbackPage({ searchParams = {} }: OAuthCallbackPageProps) {
  const code = asString(searchParams.code);
  const state = asString(searchParams.state);

  return <OAuthCallbackClient code={code} state={state} />;
}
