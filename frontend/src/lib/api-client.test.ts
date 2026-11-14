import { describe, expect, it, vi } from "vitest";
import { api } from "./api-client";

describe("API client", () => {
  it("retries a safe request once after a server error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("{}", { status: 503, headers: { "Content-Type": "application/json" } }),
      )
      .mockResolvedValueOnce(
        new Response('{"status":"ok"}', {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    await expect(api<{ status: string }>("/health")).resolves.toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.unstubAllGlobals();
  });

  it("does not retry a mutation after a server error", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"error":"unavailable"}', {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(api("/sessions", { method: "POST", body: "{}" })).rejects.toThrow("unavailable");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });
});
