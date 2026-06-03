import type { ArbType, MarketType, OpportunityStatus } from './entities.js';

export interface OpportunityLeg {
  sportsbookId: string;
  sportsbookName: string;
  outcomeId: string;
  outcomeLabel: string;
  decimalOdds: number;
  impliedProb: number;
  suggestedStake: number;
  sideLabel: string;
}

export interface ArbitrageOpportunityDto {
  id: string;
  eventId: string;
  marketType: MarketType;
  createdAt: string;
  status: OpportunityStatus;
  arbType: ArbType;
  marginPct: number;
  legs: OpportunityLeg[];
  detectionReason: string;
  marketRiskScore: number;
  dataFreshnessScore: number;
  executionDifficulty: number;
  event?: {
    homeTeam: string;
    awayTeam: string;
    startTime: string;
    leagueName?: string;
    sportName?: string;
  };
  totalSuggestedStake?: number;
  theoreticalProfit?: number;
}

export interface OpportunityFilters {
  sportId?: string;
  leagueId?: string;
  marketType?: MarketType;
  minEdgePct?: number;
  status?: OpportunityStatus;
  minMinutesToStart?: number;
  sportsbookIds?: string[];
}
