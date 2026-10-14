export interface ApiError extends Error {
  status?: number;
  code: "timeout" | "network" | "http" | "invalid-response";
}

export interface HealthResponse {
  status: string;
  database?: string;
  dataset?: string;
  [key: string]: unknown;
}

export interface Dataset {
  id: string;
  name: string;
  description?: string;
}

export interface DatasetColumn {
  name: string;
  type: string;
  primary_key?: boolean;
  foreign_key?: string | null;
}

export interface DatasetTable {
  name: string;
  columns: DatasetColumn[];
  row_count?: number;
  sample_rows?: Record<string, unknown>[];
}

export interface DatasetSchema {
  dataset?: string;
  tables: DatasetTable[];
  relationships?: { from: string; to: string; columns?: string }[];
}

export interface AnalysisRequest {
  question: string;
  dataset?: string;
  max_rows?: number;
}

export interface SqlResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count?: number;
  execution_time_ms?: number;
  status?: string;
}

export interface ChartConfiguration {
  type: "bar" | "line" | "pie" | "table";
  title?: string;
  x_axis?: string;
  y_axis?: string;
}

export interface AnalysisResponse {
  answer: string;
  findings?: string[];
  sql: string;
  result: SqlResult;
  chart?: ChartConfiguration;
  execution_time_ms?: number;
  correction_attempts?: number;
  status?: string;
}

export interface EvaluationReport {
  metrics?: {
    execution_success_rate?: number;
    correctness_rate?: number;
    safety_pass_rate?: number;
    average_latency_ms?: number;
    total_test_cases?: number;
  };
  history?: Record<string, unknown>[];
  failures?: Record<string, unknown>[];
  difficulty?: Record<string, unknown>[];
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const timeoutMs = 15_000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      const error = new Error(`The service returned ${response.status}.`) as ApiError;
      error.status = response.status;
      error.code = "http";
      throw error;
    }
    return (await response.json()) as T;
  } catch (caught) {
    if (caught instanceof Error && "code" in caught) throw caught;
    const error = new Error(
      caught instanceof Error && caught.name === "AbortError"
        ? "The request took too long. Try again."
        : "Unable to reach the analytics service. Check that the backend is running and the API URL is correct.",
    ) as ApiError;
    error.code = caught instanceof Error && caught.name === "AbortError" ? "timeout" : "network";
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  schema: () => request<DatasetSchema>("/api/schema"),
  datasets: () => request<Dataset[] | { datasets: Dataset[] }>("/api/datasets"),
  analyze: (body: AnalysisRequest) =>
    request<AnalysisResponse>("/api/analyze", { method: "POST", body: JSON.stringify(body) }),
  query: (sql: string) => request<SqlResult>("/api/query", { method: "POST", body: JSON.stringify({ sql }) }),
  evaluation: () => request<EvaluationReport>("/api/evaluation"),
  runEvaluation: () => request<EvaluationReport>("/api/evaluation/run", { method: "POST", body: "{}" }),
};

export function apiBaseUrl() {
  return baseUrl;
}