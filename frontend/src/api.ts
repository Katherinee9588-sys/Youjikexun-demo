import type {
  AppOverview,
  CompanionGenerationRequest,
  DailySummary,
  GroundedCompanionResponse,
  KnowledgePreview,
  KnowledgeQuery,
  LedgerEntry,
  RAGStatus,
  TrendsReport,
  UserEntryCreate,
  VoiceTranscript,
} from "./types";

const API_ROOT = "/api";

function isLedgerEntry(value: unknown): value is LedgerEntry {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.id === "string"
    && typeof entry.record_date === "string"
    && typeof entry.original_text === "string"
    && typeof entry.input_method === "string"
    && typeof entry.extraction_status === "string"
  );
}

function isVoiceTranscript(value: unknown): value is VoiceTranscript {
  if (typeof value !== "object" || value === null) return false;
  const transcript = value as Record<string, unknown>;
  return typeof transcript.text === "string" && transcript.text.trim().length > 0;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  if (!response.ok) {
    const contentType = response.headers.get("content-type");
    if (contentType !== null && contentType.includes("application/json")) {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") throw new Error(payload.detail);
    }
    throw new Error(`请求失败（${response.status} ${response.statusText}）`);
  }
  return (await response.json()) as T;
}

export function getOverview(signal?: AbortSignal): Promise<AppOverview> {
  return request<AppOverview>("/overview", { signal });
}

export function getLedger(signal?: AbortSignal): Promise<LedgerEntry[]> {
  return request<LedgerEntry[]>("/ledger?limit=100", { signal });
}

export function getDailySummaries(signal?: AbortSignal): Promise<DailySummary[]> {
  return request<DailySummary[]>("/daily-summaries", { signal });
}

export function getTrends(signal?: AbortSignal): Promise<TrendsReport> {
  return request<TrendsReport>("/trends", { signal });
}

export async function saveTextEntry(payload: UserEntryCreate): Promise<LedgerEntry> {
  const response = await request<unknown>("/entries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!isLedgerEntry(response)) {
    throw new Error("记录保存响应格式不正确，未进入已保存页面。");
  }
  return response;
}

export async function transcribeVoice(audio: ArrayBuffer): Promise<string> {
  const response = await request<unknown>("/voice/transcriptions", {
    method: "POST",
    headers: { "Content-Type": "audio/wav" },
    body: audio,
  });
  if (!isVoiceTranscript(response)) {
    throw new Error("语音转写响应格式不正确。");
  }
  return response.text;
}

export function getKnowledgeStatus(signal?: AbortSignal): Promise<RAGStatus> {
  return request<RAGStatus>("/knowledge/status", { signal });
}

export function previewKnowledge(payload: KnowledgeQuery): Promise<KnowledgePreview> {
  return request<KnowledgePreview>("/knowledge/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function generateCompanion(
  payload: CompanionGenerationRequest,
): Promise<GroundedCompanionResponse> {
  return request<GroundedCompanionResponse>("/companion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
