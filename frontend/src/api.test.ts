// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
describe("workspace API client", () => {
  it("keeps the workspace token in authorization headers and sends JSON", async () => {
    sessionStorage.setItem("lingua-token", "workspace-secret");
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ results: [] }) });
    vi.stubGlobal("fetch", fetch);
    await api("/search", {
      method: "POST",
      body: JSON.stringify({ query: "identity" }),
    });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/search");
    expect(options.headers.get("Authorization")).toBe(
      "Bearer workspace-secret",
    );
    expect(options.headers.get("Content-Type")).toBe("application/json");
  });
  it("lets the browser set the multipart boundary for uploads", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ id: "test" }) });
    vi.stubGlobal("fetch", fetch);
    await api("/documents", { method: "POST", body: new FormData() });
    expect(fetch.mock.calls[0][1].headers.has("Content-Type")).toBe(false);
  });
  it("surfaces actionable server errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 401,
          json: async () => ({
            detail: "Enter your workspace access token in Settings.",
          }),
        }),
    );
    await expect(api("/documents")).rejects.toThrow("workspace access token");
  });
  it("handles non-JSON upstream errors without crashing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => {
          throw new Error("Bad JSON");
        },
      }),
    );
    await expect(api("/documents")).rejects.toThrow("502");
  });
});
