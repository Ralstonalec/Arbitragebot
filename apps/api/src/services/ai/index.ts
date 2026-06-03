import type {
  ExplainOpportunityRequest,
  ExplainOpportunityResponse,
  NormalizeEntitiesRequest,
  NormalizeEntitiesResponse,
  StrategyReviewRequest,
  StrategyReviewResponse,
} from '@arb/shared';
import { config } from '../../config.js';

const STUB_MODEL = 'template-stub-v1';

/**
 * AI service boundary — swap implementations when OPENAI_API_KEY is set.
 */
export class AiService {
  async explainOpportunity(
    req: ExplainOpportunityRequest,
  ): Promise<ExplainOpportunityResponse> {
    if (config.OPENAI_API_KEY) {
      // Future: call OpenAI with structured output
    }
    return explainOpportunityStub(req);
  }

  async normalizeEntities(
    req: NormalizeEntitiesRequest,
  ): Promise<NormalizeEntitiesResponse> {
    if (config.OPENAI_API_KEY) {
      // Future: LLM-assisted fuzzy match
    }
    return normalizeEntitiesStub(req);
  }

  async strategyReview(
    req: StrategyReviewRequest,
  ): Promise<StrategyReviewResponse> {
    if (config.OPENAI_API_KEY) {
      // Future: periodic health check via LLM
    }
    return strategyReviewStub(req);
  }
}

export const aiService = new AiService();

function explainOpportunityStub(
  req: ExplainOpportunityRequest,
): ExplainOpportunityResponse {
  const o = req.opportunity;
  const books = o.legs.map((l) => l.sportsbookName).join(', ');
  const brief = `Theoretical ${o.arbType.replace('_', '-')} edge ${o.marginPct.toFixed(2)}% on ${o.event?.awayTeam ?? 'event'} @ ${o.event?.homeTeam ?? ''} (${books}).`;
  const detailed = [
    `## Opportunity overview`,
    `This is a **theoretical arbitrage** (${o.arbType}) with estimated margin **${o.marginPct.toFixed(2)}%** before execution risk.`,
    ``,
    `**Event:** ${o.event?.homeTeam ?? 'Home'} vs ${o.event?.awayTeam ?? 'Away'}`,
    `**Market:** ${o.marketType}`,
    `**Detection:** ${o.detectionReason}`,
    ``,
    `### Legs`,
    ...o.legs.map(
      (l) =>
        `- **${l.sportsbookName}** — ${l.sideLabel} @ ${l.decimalOdds} (suggested stake ${l.suggestedStake})`,
    ),
    ``,
    `### Risk signals`,
    `- Data freshness score: ${o.dataFreshnessScore}/100`,
    `- Market risk score: ${o.marketRiskScore}/100`,
    `- Execution difficulty: ${o.executionDifficulty}/100`,
    ``,
    `### What can go wrong`,
    `- Odds may move before all legs are placed.`,
    `- Sportsbooks may limit or reject bets.`,
    `- Palpable error or void rules may apply.`,
    ``,
    `This tool does not place bets or hold funds. You execute manually at external licensed books.`,
  ].join('\n');

  return { briefText: brief, detailedText: detailed, modelName: STUB_MODEL };
}

function normalizeEntitiesStub(
  req: NormalizeEntitiesRequest,
): NormalizeEntitiesResponse {
  return {
    modelName: STUB_MODEL,
    matches: req.candidates.map((c) => ({
      externalLabel: c.externalLabel,
      suggestedCanonicalLabel: c.externalLabel.trim(),
      confidence: 0.6,
      needsReview: true,
    })),
  };
}

function strategyReviewStub(
  req: StrategyReviewRequest,
): StrategyReviewResponse {
  return {
    modelName: STUB_MODEL,
    summary:
      `Review for the last ${req.periodDays} days (stub). ` +
      `Analyze action logs and P&L when real data is available.`,
    suggestions: [
      {
        parameter: 'minArbEdgePct',
        current: req.currentSettings.minArbEdgePct ?? 0.5,
        suggested: 0.75,
        rationale:
          'Stub suggestion: slightly higher minimum edge may reduce false positives from stale lines.',
      },
    ],
  };
}
