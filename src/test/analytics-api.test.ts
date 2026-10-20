import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiBaseUrl } from "@/services/api";

describe("analytics API service", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the local Python backend by default and loads datasets from it", async () => {
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000");

    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([{ id: "sales", name: "Retail sales" }]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.datasets()).resolves.toEqual([{ id: "sales", name: "Retail sales" }]);
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/datasets", expect.objectContaining({
      headers: { "Content-Type": "application/json" },
    }));
  });

  it("sends the selected dataset and analysis payload to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ answer: "Real response", sql: "SELECT 1", result: { columns: [], rows: [] } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.analyze({ question: "Show total sales", dataset: "sales", max_rows: 25 });
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/analyze", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "Show total sales", dataset: "sales", max_rows: 25 }),
    }));
  });

  it("surfaces backend errors instead of returning sample results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    await expect(api.health()).rejects.toMatchObject({ code: "http", status: 503 });
  });
});