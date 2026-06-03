import type { ArbitrageOpportunityDto } from './opportunity.js';

export interface ExplainOpportunityRequest {
  opportunity: ArbitrageOpportunityDto;
  userSettingsSummary?: Record<string, unknown>;
}

export interface ExplainOpportunityResponse {
  briefText: string;
  detailedText: string;
  modelName: string;
}

export interface NormalizeEntitiesRequest {
  candidates: Array<{
    providerCode: string;
    entityType: 'team' | 'league' | 'event';
    externalLabel: string;
    context?: string;
  }>;
}

export interface NormalizeEntitiesResponse {
  matches: Array<{
    externalLabel: string;
    suggestedCanonicalId?: string;
    suggestedCanonicalLabel?: string;
    confidence: number;
    needsReview: boolean;
  }>;
  modelName: string;
}

export interface StrategyReviewRequest {
  periodDays: number;
  actionLogSummary: Record<string, number>;
  pnlSummary?: Record<string, number>;
  currentSettings: Record<string, unknown>;
}

export interface StrategyReviewResponse {
  summary: string;
  suggestions: Array<{ parameter: string; current: unknown; suggested: unknown; rationale: string }>;
  modelName: string;
}
