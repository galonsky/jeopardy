export type MutatorConfig = {
  url: string;
  method?: string;
  params?: Record<string, string | number | boolean | undefined>;
  data?: unknown;
};

export async function customInstance<T>(
  config: string | MutatorConfig,
  options?: RequestInit,
): Promise<T> {
  const path = typeof config === "string" ? config : config.url;
  const method = (
    (typeof config === "string" ? options?.method : (config.method ?? options?.method)) ?? "GET"
  ).toUpperCase();
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const url = new URL(
    path.startsWith("/api/") ? path : `/api${path.startsWith("/") ? path : `/${path}`}`,
    origin,
  );
  if (typeof config !== "string") {
    for (const [key, value] of Object.entries(config.params ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  const headers = new Headers(options?.headers);
  const body =
    typeof config === "string"
      ? options?.body
      : config.data === undefined
        ? options?.body
        : JSON.stringify(config.data);
  if (body) headers.set("Content-Type", "application/json");
  const csrf =
    typeof document === "undefined"
      ? undefined
      : document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)?.[1];
  if (csrf && !["GET", "HEAD", "OPTIONS"].includes(method))
    headers.set("X-CSRFToken", decodeURIComponent(csrf));
  let response = await fetch(url, {
    ...options,
    method,
    body,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 401 && typeof window !== "undefined")
    window.location.assign("/oidc/login/");
  if (response.status >= 500 && ["GET", "HEAD", "OPTIONS"].includes(method)) {
    response = await fetch(url, { ...options, method, body, headers, credentials: "same-origin" });
  }
  if (response.status === 204) return undefined as T;
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result as T;
}

export function api<T>(path: string, options?: RequestInit): Promise<T> {
  return customInstance<T>(path, options);
}
