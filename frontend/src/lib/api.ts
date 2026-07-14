import type { HealthResponse, IngestResponse, QueryRequest, QueryResponse } from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export async function ingestDocument(
  file: File,
  documentName: string,
  version: string,
): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_name", documentName);
  formData.append("version", version);

  const controller = new AbortController();
  const timeoutMs = 300_000;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/ingest`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    return handleResponse<IngestResponse>(response);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "Ingestion timed out after 5 minutes. Large PDFs with many tables can take several minutes — try again or check backend logs.",
        408,
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function query(request: QueryRequest): Promise<QueryResponse> {
  const controller = new AbortController();
  const timeoutMs = 180_000;
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    return handleResponse<QueryResponse>(response);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "Request timed out after 3 minutes. Compare and summary can take 30–90 seconds when the AI API is busy — try again shortly.",
        408,
      );
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  return handleResponse<HealthResponse>(response);
}
