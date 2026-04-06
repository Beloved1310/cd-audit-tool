/** Journey audit API — matches backend/schemas/journey.py */

import type { DarkPattern } from "./audit";

export interface JourneyStepInput {
  label: string;
  url: string;
}

export interface JourneyStepResult {
  step_index: number;
  label: string;
  url: string;
  page_title: string;
  word_count: number;
  fetch_error: string | null;
  friction_flags: string[];
  friction_evidence_quotes: string[];
  dark_patterns: DarkPattern[];
  step_summary: string;
}

export interface JourneyReport {
  generated_at: string;
  steps: JourneyStepResult[];
}
