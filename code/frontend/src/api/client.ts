import type {
  AuditLogEntry,
  ComplianceAssessment,
  ImpactReviewItem,
  QaRequest,
  QaResponse,
  ReportFilter,
  ReportResponse,
  TransactionPayload,
  UserRole,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors?: { field: string; message: string }[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? "request failed", body.errors);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function issueDevToken(userId: string, role: UserRole): Promise<{ access_token: string }> {
  return request("/auth/dev-token", { method: "POST", body: JSON.stringify({ user_id: userId, role }) });
}

export function askQuestion(payload: QaRequest, token: string): Promise<QaResponse> {
  return request("/qa", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function screenTransaction(payload: TransactionPayload, token: string): Promise<ComplianceAssessment> {
  return request("/screening", { method: "POST", body: JSON.stringify(payload) }, token);
}

export function generateReport(filters: ReportFilter, token: string): Promise<ReportResponse> {
  return request("/reports", { method: "POST", body: JSON.stringify(filters) }, token);
}

export async function downloadReportPdf(reportId: string, token: string): Promise<Blob> {
  // A plain <a href> can't attach an Authorization header, so the PDF is
  // fetched as a blob and handed to the browser via an object URL instead.
  const response = await fetch(`${BASE_URL}/reports/${reportId}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new ApiError(response.status, "failed to download PDF");
  return response.blob();
}

export function getImpactReviewQueue(token: string): Promise<ImpactReviewItem[]> {
  return request("/impact-review-queue", { method: "GET" }, token);
}

export function getAuditLog(token: string): Promise<AuditLogEntry[]> {
  return request("/audit-log", { method: "GET" }, token);
}
