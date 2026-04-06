import type { AuditResponse, ComparisonReport } from "@/types/audit";
import type { JourneyReport, JourneyStepInput } from "@/types/journey";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export type ApiErrorInfo = {
  message: string;
  requestId?: string;
  status?: number;
};

async function parseApiError(res: Response): Promise<ApiErrorInfo> {
  const requestId = res.headers.get("X-Request-ID") || undefined;
  const status = res.status;

  let rawText = "";
  try {
    rawText = await res.text();
  } catch {
    rawText = "";
  }

  // Prefer structured backend errors.
  try {
    const j = rawText ? (JSON.parse(rawText) as any) : null;
    const msg =
      j?.error?.message ||
      j?.detail ||
      (typeof j === "string" ? j : "") ||
      res.statusText ||
      "Request failed";
    return { message: String(msg), requestId: j?.request_id || requestId, status };
  } catch {
    // Fall back to plain text.
    const msg = rawText || res.statusText || "Request failed";
    return { message: msg, requestId, status };
  }
}

export async function runAudit(url: string): Promise<AuditResponse> {
  const res = await fetch(`${API_BASE}/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    throw await parseApiError(res);
  }
  return res.json() as Promise<AuditResponse>;
}

export async function runCompare(
  url_a: string,
  url_b: string,
): Promise<ComparisonReport> {
  const res = await fetch(`${API_BASE}/audit/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url_a, url_b }),
  });
  if (!res.ok) {
    throw await parseApiError(res);
  }
  return res.json() as Promise<ComparisonReport>;
}

export async function runJourney(
  steps: JourneyStepInput[],
): Promise<JourneyReport> {
  const res = await fetch(`${API_BASE}/audit/journey`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ steps }),
  });
  if (!res.ok) {
    throw await parseApiError(res);
  }
  return res.json() as Promise<JourneyReport>;
}
