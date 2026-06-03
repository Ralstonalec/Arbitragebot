import type { ArbitrageOpportunityDto } from '@arb/shared';
import type { Prisma } from '@prisma/client';

type OppWithRelations = Prisma.ArbitrageOpportunityGetPayload<{
  include: {
    legs: { include: { sportsbook: true } };
    event: { include: { league: { include: { sport: true } } } };
    explanations: { orderBy: { createdAt: 'desc' }; take: 1 };
  };
}>;

export function mapOpportunity(opp: OppWithRelations): ArbitrageOpportunityDto {
  return {
    id: opp.id,
    eventId: opp.eventId,
    marketType: opp.marketType,
    createdAt: opp.createdAt.toISOString(),
    status: opp.status,
    arbType: opp.arbType,
    marginPct: opp.marginPct.toNumber(),
    detectionReason: opp.detectionReason,
    marketRiskScore: opp.marketRiskScore,
    dataFreshnessScore: opp.dataFreshnessScore,
    executionDifficulty: opp.executionDifficulty,
    totalSuggestedStake: opp.totalSuggestedStake?.toNumber(),
    theoreticalProfit: opp.theoreticalProfit?.toNumber(),
    legs: opp.legs.map((leg) => ({
      sportsbookId: leg.sportsbookId,
      sportsbookName: leg.sportsbook.name,
      outcomeId: leg.outcomeId,
      outcomeLabel: leg.sideLabel,
      decimalOdds: leg.decimalOdds.toNumber(),
      impliedProb: leg.impliedProb.toNumber(),
      suggestedStake: leg.suggestedStake.toNumber(),
      sideLabel: leg.sideLabel,
    })),
    event: {
      homeTeam: opp.event.homeTeam,
      awayTeam: opp.event.awayTeam,
      startTime: opp.event.startTime.toISOString(),
      leagueName: opp.event.league.name,
      sportName: opp.event.league.sport.name,
    },
  };
}
