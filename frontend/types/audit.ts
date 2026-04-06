/** Matches backend Pydantic schemas */

/** PRIN 2A.2–2A.5 order — matches backend :meth:`AuditReport.compute_overall`. */
export const OUTCOME_DISPLAY_ORDER = [
  "Products & Services",
  "Price & Value",
  "Consumer Understanding",
  "Consumer Support",
] as const;

export type RAGRating = "RED" | "AMBER" | "GREEN";

export type ConfidenceLevel = "high" | "medium" | "low";

export type AuditStatus = "complete" | "insufficient_data" | "crawl_failed";

export type AssessmentScope = "public_website_only" | "internal_and_public";

export interface CriterionScore {
  criterion_id: number;
  criterion_name: string;
  max_points: number;
  awarded_points: number;
  met: boolean;
  evidence: string;
  page_url: string;
}

export interface Finding {
  description: string;
  page_url: string;
  evidence_text: string;
  fca_reference: string;
  severity: "critical" | "moderate" | "minor";
}

export interface DarkPattern {
  pattern_type: string;
  description: string;
  page_url: string;
  evidence_text: string;
}

export interface VulnerabilityGap {
  gap_type: string;
  description: string;
  fca_reference: string;
}

export interface OutcomeScore {
  assessment_scope: AssessmentScope;
  scope_note: string;
  outcome_name: string;
  rating: RAGRating;
  score: number;
  confidence: ConfidenceLevel;
  confidence_note: string;
  summary: string;
  criteria_scores: CriterionScore[];
  findings: Finding[];
  recommendations: string[];
}

export interface AuditReport {
  insufficient_data: false;
  url: string;
  audited_at: string;
  status: AuditStatus;
  overall_rating: RAGRating | null;
  overall_score: number | null;
  outcomes: OutcomeScore[];
  dark_patterns: DarkPattern[];
  vulnerability_gaps: VulnerabilityGap[];
  pages_crawled: string[];
  total_words_analysed: number;
  crawl_duration_seconds: number;
  pipeline_duration_seconds: number;
  insufficient_data_reason: string | null;
}

export interface InsufficientDataReport {
  insufficient_data: true;
  url: string;
  audited_at: string;
  status: AuditStatus;
  reason: string;
  pages_crawled: string[];
  total_words_analysed: number;
  crawl_duration_seconds: number;
  pipeline_duration_seconds: number;
}

export interface ComparisonReport {
  url_a: string;
  url_b: string;
  hash_a: string;
  hash_b: string;
  report_a: AuditReport | InsufficientDataReport;
  report_b: AuditReport | InsufficientDataReport;
  generated_at_iso: string;
  both_sufficient: boolean;
}

export type AuditResponse = AuditReport | InsufficientDataReport;
