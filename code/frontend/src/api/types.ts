// Mirrors backend/schemas/*.py and shared/models/*.py — kept in sync by hand
// for this MVP (a generated OpenAPI client is the natural upgrade path).

export type UserRole = "compliance_officer" | "compliance_head" | "internal_auditor" | "platform_admin";

export type RiskRating = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface QaRequest {
  query: string;
  jurisdictions?: string[];
  framework?: string;
  as_of?: string;
}

export interface QaResponse {
  answer: string;
  status: "answered" | "insufficient_context" | "off_topic" | "degraded";
  citations: string[];
  provenance: Record<string, unknown> | null;
}

export interface TransactionPayload {
  transaction_id?: string;
  amount: number;
  currency: string;
  counterparty: string;
  counterparty_kyc_status: "verified" | "pending" | "not_verified" | "unknown";
  jurisdictions: string[];
  instrument_type: string;
  customer_type: "retail" | "institutional" | "intra_group";
  transaction_type: "cross_border_payment" | "derivative_trade" | "investment" | "lending";
  is_appropriateness_assessed?: boolean | null;
  is_priority_sector?: boolean | null;
  counterparty_jurisdiction_risk?: string | null;
}

export interface Citation {
  citation_key: string;
  doc_id: string;
  clause_id: string;
  version: string;
  framework: string;
  title: string;
  snippet: string;
}

export interface RuleTrigger {
  rule_id: string;
  description: string;
  framework: string;
  severity: RiskRating;
  citations: Citation[];
}

export interface RequiredAction {
  action: string;
  reason: string;
  citations: Citation[];
}

export interface FrameworkConflict {
  description: string;
  conflicting_rules: string[];
}

export interface ComplianceAssessment {
  transaction_id: string | null;
  status: "completed" | "needs_review" | "degraded";
  applicable_frameworks: string[];
  risk_rating: RiskRating;
  rule_triggers: RuleTrigger[];
  required_actions: RequiredAction[];
  citations: Citation[];
  assumptions: string[];
  missing_facts: string[];
  conflicts: FrameworkConflict[];
  confidence_score: number;
  narrative: string;
  provenance: Record<string, unknown> | null;
}

export interface ReportFilter {
  date_from?: string;
  date_to?: string;
  transaction_type?: string;
  jurisdiction?: string;
  min_risk_rating?: string;
}

export interface ReportResponse {
  report_id: string;
  filters: Record<string, unknown>;
  summary_stats: Record<string, unknown>;
  narrative: string;
  markdown: string;
  transaction_count: number;
}

export interface ImpactReviewItem {
  id: number;
  new_doc_id: string;
  superseded_doc_id: string | null;
  changed_clauses: Record<string, unknown>[];
  affected_transaction_types: string[];
  status: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  request_id: string;
  user_id: string;
  role: string;
  endpoint: string;
  input_redacted: Record<string, unknown>;
  retrieved_chunk_ids: string[];
  model_id: string | null;
  model_version: string | null;
  prompt_template_id: string | null;
  prompt_template_version: string | null;
  output_redacted: Record<string, unknown>;
  confidence_score: number | null;
  human_override: Record<string, unknown> | null;
  created_at: string;
}
