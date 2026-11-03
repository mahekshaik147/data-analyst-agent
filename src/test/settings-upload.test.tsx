import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { uploadDatasetMock, deleteDatasetMock, datasetsMock } = vi.hoisted(() => ({
  uploadDatasetMock: vi.fn(),
  deleteDatasetMock: vi.fn(),
  datasetsMock: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  Link: ({ children, ...props }: any) => <a {...props}>{children}</a>,
  Outlet: () => null,
  useRouterState: () => ({ location: { pathname: "/settings" } }),
}));

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      health: vi.fn(),
      datasets: datasetsMock,
      uploadDataset: uploadDatasetMock,
      deleteDataset: deleteDatasetMock,
    },
  };
});

import { SettingsPage } from "@/components/analytics/workspace";

describe("Settings upload form", () => {
  it("renders a visible dataset name field, file picker, and upload submit button and submits multipart data", async () => {
    uploadDatasetMock.mockResolvedValue({
      status: "ok",
      dataset: { id: "uploaded-sales", name: "Uploaded sales" },
      table_name: "uploaded_data",
      row_count: 5,
    });

    render(<SettingsPage />);

    expect(screen.getByLabelText(/dataset name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/csv file/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /upload csv/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/dataset name/i), {
      target: { value: "Quarterly revenue" },
    });

    const file = new File(["region,sales\nNorth,120\n"], "quarterly.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText(/csv file/i), {
      target: { files: [file] },
    });

    fireEvent.click(screen.getByRole("button", { name: /upload csv/i }));

    await waitFor(() => {
      expect(uploadDatasetMock).toHaveBeenCalledTimes(1);
    });

    expect(uploadDatasetMock).toHaveBeenCalledWith(file, "Quarterly revenue");
  });

  it("lists uploaded datasets only and confirms deletion before removing one", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteDatasetMock.mockResolvedValue({ status: "ok", dataset_id: "uploaded-forecast" });

    datasetsMock.mockResolvedValue([
      { id: "sales", name: "Retail sales" },
      { id: "olist", name: "Olist" },
      { id: "uploaded-forecast", name: "Forecast" },
    ]);

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/uploaded datasets/i)).toBeInTheDocument();
    });

    expect(screen.getByText("Forecast")).toBeInTheDocument();
    expect(screen.queryByText("Retail sales")).not.toBeInTheDocument();
    expect(screen.queryByText("Olist")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /delete forecast/i }));

    await waitFor(() => {
      expect(deleteDatasetMock).toHaveBeenCalledWith("uploaded-forecast");
    });

    expect(confirmSpy).toHaveBeenCalledWith("Delete the uploaded dataset \"Forecast\"?");
    confirmSpy.mockRestore();
  });
});
