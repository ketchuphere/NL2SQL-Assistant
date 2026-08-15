/**
 * src/lib/api.ts
 * Real API client wired to the NL2SQL RAG FastAPI backend.
 */
import axios from "axios";

export type Feedback = "up" | "down" | null;

export interface SqlResult {
  columns: string[];
  rows: (string | number | null)[][];
}

export type ThinkingStage =
  | "understanding"
  | "schema"
  | "generating"
  | "executing"
  | "done";

export interface AssistantPayload {
  sql: string;
  explanation: string;
  result: SqlResult;
  durationMs: number;
  confidence: number;
  followUps: string[];
  tablesUsed: string[];
  intermediateSqls: string[];
  assumptions: string;
  requestId: string;
  sessionId: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  payload?: AssistantPayload;
  feedback?: Feedback;
  isLoading?: boolean;
  stage?: ThinkingStage;
  error?: string;
  errorFix?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
  /** Backend session ID for multi-turn context */
  sessionId?: string;
}

export interface SavedQuery {
  id: string;
  title: string;
  sql: string;
  createdAt: number;
}

export interface SchemaColumn {
  name: string;
  type: string;
  pk?: boolean;
  fk?: string;
}

export interface SchemaTable {
  name: string;
  schema: string;
  rowCount: number;
  columns: SchemaColumn[];
}

export interface DatabaseInfo {
  name: string;
  engine: string;
  host: string;
  status: "connected" | "disconnected";
  tables: SchemaTable[];
  vectorCount: number;
}

// Backend response shapes
interface BackendQueryResponse {
  request_id: string;
  question: string;
  generated_sql: string;
  intermediate_sqls: string[];
  rows: Record<string, string | number | null>[];
  row_count: number;
  explanation: string;
  assumptions: string;
  success: boolean;
  error: string;
  latency: {
    retrieval_ms: number;
    generation_ms: number;
    execution_ms: number;
    total_ms: number;
  };
  session_id: string;
  tables_used?: string[];
}

interface BackendSchemaResponse {
  tables: Array<{
    table_schema: string;
    table_name: string;
    columns: Array<{
      column_name: string;
      data_type: string;
      is_primary_key: string;
      referenced_table?: string;
    }>;
  }>;
  db_name: string;
  db_type: string;
  host: string;
}

interface BackendStatusResponse {
  collection_name: string;
  vector_count: number;
  status: string;
}

// Axios client — proxied to http://localhost:8000 via vite.config.ts
export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function rowsToSqlResult(rows: Record<string, string | number | null>[]): SqlResult {
  if (!rows || rows.length === 0) return { columns: [], rows: [] };
  const columns = Object.keys(rows[0]);
  return { columns, rows: rows.map((r) => columns.map((c) => r[c] ?? null)) };
}

function deriveConfidence(res: BackendQueryResponse): number {
  if (!res.success) return 0;
  const latencyBonus = Math.max(0, 1 - res.latency.generation_ms / 3000);
  const noIntermediateBonus = res.intermediate_sqls.length === 0 ? 0.05 : 0;
  return Math.min(0.99, 0.85 + latencyBonus * 0.1 + noIntermediateBonus);
}

function generateFollowUps(question: string, sql: string): string[] {
  const q = question.toLowerCase();
  const s = sql.toLowerCase();
  const suggestions: string[] = [];
  if (q.includes("top") || q.includes("limit")) suggestions.push("Show me the bottom 10 instead");
  if (q.includes("count") || q.includes("how many")) suggestions.push("Break this down by date");
  if (q.includes("revenue") || q.includes("total") || q.includes("sum")) suggestions.push("Group by month instead");
  if (s.includes("join")) suggestions.push("Add more columns to the result");
  if (suggestions.length < 2) {
    suggestions.push("Filter for last month only");
    suggestions.push("Show me a trend over time");
  }
  return suggestions.slice(0, 3);
}

function mapToPayload(res: BackendQueryResponse): AssistantPayload {
  return {
    sql: res.generated_sql || res.intermediate_sqls?.[0] || "",
    explanation: res.explanation || (res.error ? `Error: ${res.error}` : ""),
    result: rowsToSqlResult(res.rows),
    durationMs: res.latency?.total_ms ?? 0,
    confidence: deriveConfidence(res),
    followUps: generateFollowUps(res.question, res.generated_sql),
    tablesUsed: res.tables_used ?? [],
    intermediateSqls: res.intermediate_sqls ?? [],
    assumptions: res.assumptions ?? "",
    requestId: res.request_id,
    sessionId: res.session_id,
  };
}

// ── Public API functions ─────────────────────────────────────────────────────

export async function askAssistant(
  prompt: string,
  _history: ChatMessage[],
  sessionId?: string,
): Promise<AssistantPayload> {
  const { data } = await api.post<BackendQueryResponse>("/rag/query", {
    question: prompt,
    session_id: sessionId ?? null,
    execute: true,
    max_rows: 500,
  });

  if (!data.success && data.error) {
    const err = new Error(data.error) as Error & { payload?: AssistantPayload };
    err.payload = mapToPayload(data);
    throw err;
  }

  return mapToPayload(data);
}

export async function fetchDatabaseSchema(): Promise<DatabaseInfo> {
  const [schemaRes, statusRes] = await Promise.allSettled([
    api.get<BackendSchemaResponse>("/documents/schema"),
    api.get<BackendStatusResponse>("/documents/status"),
  ]);

  const schema = schemaRes.status === "fulfilled" ? schemaRes.value.data : null;
  const status = statusRes.status === "fulfilled" ? statusRes.value.data : null;

  const tables: SchemaTable[] =
    schema?.tables?.map((t) => ({
      name: t.table_name,
      schema: t.table_schema,
      rowCount: 0,
      columns: t.columns.map((c) => ({
        name: c.column_name,
        type: c.data_type,
        pk: c.is_primary_key === "YES",
        fk: c.referenced_table ?? undefined,
      })),
    })) ?? [];

  return {
    name: schema?.db_name ?? "Database",
    engine: schema?.db_type ?? "PostgreSQL",
    host: schema?.host ?? "localhost",
    status: tables.length > 0 ? "connected" : "disconnected",
    tables,
    vectorCount: status?.vector_count ?? 0,
  };
}

export async function indexSchema(params: {
  db_type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
}): Promise<{ documents_indexed: number }> {
  const { data } = await api.post("/documents/index", params);
  return data;
}

export async function sendFeedback(
  messageId: string,
  value: Exclude<Feedback, null>,
): Promise<void> {
  console.info("[feedback]", messageId, value);
}

// Fallback placeholder used before first schema fetch
export const MOCK_DATABASE: DatabaseInfo = {
  name: "Connecting…",
  engine: "PostgreSQL",
  host: "localhost",
  status: "disconnected",
  tables: [],
  vectorCount: 0,
};
