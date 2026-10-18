import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api";

describe("analytics API service", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends the requested natural-language analysis to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Real response",
          sql: "SELECT 1",
          result: { columns: [], rows: [] },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await api.analyze({ question: "Show total sales", dataset: "northwind", max_rows: 25 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/analyze",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "Show total sales", dataset: "northwind", max_rows: 25 }),
      }),
    );
  });

  it("surfaces backend errors instead of returning sample results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    await expect(api.health()).rejects.toMatchObject({ code: "http", status: 503 });
  });
});
