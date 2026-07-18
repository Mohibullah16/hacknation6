/** Typed client for the RealDoor API. All calls are same-origin (/api proxy). */

export interface FieldValue {
  field: string;
  value: string | number | null;
  page: number | null;
  bbox: number[] | null;
  bbox_units: string;
  confidence: number;
  status: "extracted" | "abstained" | "confirmed" | "corrected";
  document_id: string;
}

export interface DocumentExtraction {
  document_id: string;
  household_id: string;
  document_type: string;
  file_name: string;
  rasterized: boolean;
  fields: FieldValue[];
  adversarial_text_detected: boolean;
  adversarial_note: string;
}

export interface IncomeSource {
  source_type: string;
  document_id: string;
  amount: number;
  frequency: string;
  annualized: number;
  formula: string;
  citations: Record<string, unknown>[];
  flags: string[];
}

export interface CalcResult {
  household_id: string;
  household_size: number | null;
  sources: IncomeSource[];
  annualized_income: number;
  threshold: number | null;
  comparison: string;
  threshold_rule_id: string | null;
  threshold_effective_date: string | null;
  threshold_source_url: string | null;
  formula: string;
}

export interface ReadinessReason {
  code: string;
  detail: string;
  rule_id: string;
}

export interface ReadinessResult {
  household_id: string;
  readiness_status: "READY_TO_REVIEW" | "NEEDS_REVIEW";
  reasons: ReadinessReason[];
  checklist_gaps: { document_type: string; status: string; guidance: string }[];
}

export interface SessionState {
  session_id: string;
  household_id: string;
  household_size: number | null;
  documents: DocumentExtraction[];
  unconfirmed_fields: { document_id: string; field: string; status: string }[];
  calc: CalcResult | null;
  readiness: ReadinessResult | null;
}

export interface QAAnswer {
  answer: string;
  citations: {
    rule_id: string;
    authority: string;
    effective_date: string | null;
    source_url: string;
    source_locator: string;
    rule_text: string;
  }[];
  authority_label: string | null;
  abstained: boolean;
  refusal?: boolean;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  createSession: () =>
    req<{ session_id: string; rule_corpus_version: string }>("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ consent: true }),
    }),
  getSession: (sid: string) => req<SessionState>(`/api/session/${sid}`),
  uploadDocument: (sid: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<DocumentExtraction>(`/api/session/${sid}/documents`, { method: "POST", body: form });
  },
  updateField: (sid: string, docId: string, field: string, action: "confirm" | "correct", value?: string) =>
    req<{ field: FieldValue; calc: CalcResult | null; readiness: ReadinessResult | null }>(
      `/api/session/${sid}/documents/${docId}/fields/${field}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value }),
      },
    ),
  confirmAll: (sid: string, docId: string) =>
    req<SessionState>(`/api/session/${sid}/documents/${docId}/confirm-all`, { method: "POST" }),
  getCalculation: (sid: string) =>
    req<{ status: string; calc?: CalcResult; readiness?: ReadinessResult; unconfirmed_fields?: unknown[]; message?: string }>(
      `/api/session/${sid}/calculation`,
    ),
  askQuestion: (sid: string, question: string) =>
    req<QAAnswer>(`/api/session/${sid}/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  getPacket: (sid: string) => req<Record<string, unknown>>(`/api/session/${sid}/packet`),
  getAudit: (sid: string) => req<{ ts: number; event: string; detail: string }[]>(`/api/session/${sid}/audit`),
  deleteSession: (sid: string) =>
    req<{ deleted: boolean; message: string }>(`/api/session/${sid}`, { method: "DELETE" }),
  getRules: () => req<Record<string, unknown>[]>("/api/rules"),
  getProperties: () =>
    req<{ disclaimer: string; total_unfiltered: number; properties: Record<string, string>[] }>("/api/properties"),
  documentFileUrl: (sid: string, docId: string) => `/api/session/${sid}/documents/${docId}/file`,
  packetExportUrl: (sid: string) => `/api/session/${sid}/packet/export`,
};
