// Mirrors backend/app/application/dto/schemas.py and domain entities exactly.
// Kept as a single source-of-truth file so API shape drift is easy to spot.

export type Intent = "single_doc_chat" | "cross_doc_chat" | "compare_documents" | "executive_summary";

export interface Citation {
  document_name: string;
  version: string;
  page_number: number;
  section: string;
  chunk_id: string;
  confidence: number;
  quoted_snippet?: string;
}

export interface MissingItem {
  text: string;
  source_file: string;
  location: string;
}

export interface DiffItem {
  docA_text: string;
  docB_text: string;
  reason: string;
  sourceA: string;
  sourceB: string;
  semantic_similarity?: number;
}

export interface MatchItem {
  textA: string;
  textB: string;
  source: string;
  similarity_score?: number;
}

// Exact shape required by the challenge brief's Document Comparison Engine.
export interface ComparisonReport {
  missing: MissingItem[];
  diff: DiffItem[];
  match: MatchItem[];
}

export interface RankedChange {
  rank: number;
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  ranking_rationale: string;
}

export interface ExecutiveSummary {
  top_important_changes: RankedChange[];
  business_impact: string;
  architecture_impact: string;
  workflow_impact: string;
}

export interface QueryRequest {
  session_id: string;
  query: string;
  document_ids: string[];
}

export interface QueryResponse {
  request_id: string;
  intent: Intent;
  answer: string;
  citations: Citation[];
  comparison: ComparisonReport | null;
  executive_summary: ExecutiveSummary | null;
  is_grounded: boolean;
  confidence: number;
  warnings: string[];
  agent_trace: string[];
}

export interface IngestResponse {
  document_id: string;
  document_name: string;
  version: string;
  chunks_created: number;
  parent_chunks: number;
  child_chunks: number;
  pages_parsed?: number;
  tables_parsed?: number;
  table_rows_parsed?: number;
  ingest_warning?: string | null;
}

export interface IngestedDocument extends IngestResponse {
  label: "A" | "B";
  fileName: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: Intent;
  citations?: Citation[];
  comparison?: ComparisonReport | null;
  executiveSummary?: ExecutiveSummary | null;
  isGrounded?: boolean;
  warnings?: string[];
  agentTrace?: string[];
  createdAt: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  ai_provider: string;
  gemini_configured: boolean;
  openai_configured: boolean;
  pinecone_configured: boolean;
  redis_configured: boolean;
  token_counting: "exact" | "approximate";
}
