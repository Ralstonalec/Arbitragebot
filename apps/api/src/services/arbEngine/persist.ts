import type { DetectedOpportunity } from './detect.js';
import { prisma } from '../../lib/prisma.js';

export async function persistOpportunities(
  detected: DetectedOpportunity[],
): Promise<string[]> {
  const ids: string[] = [];

  for (const d of detected) {
    const existing = await prisma.arbitrageOpportunity.findFirst({
      where: {
        eventId: d.eventId,
        marketType: d.marketType,
        status: 'open',
      },
      include: { legs: true },
    });

    if (existing) {
      await prisma.arbitrageOpportunity.update({
        where: { id: existing.id },
        data: {
          marginPct: d.marginPct,
          detectionReason: d.detectionReason,
          marketRiskScore: d.marketRiskScore,
          dataFreshnessScore: d.dataFreshnessScore,
          executionDifficulty: d.executionDifficulty,
          totalSuggestedStake: d.totalSuggestedStake,
          theoreticalProfit: d.theoreticalProfit,
        },
      });
      await prisma.arbitrageOpportunityLeg.deleteMany({
        where: { opportunityId: existing.id },
      });
      await createLegs(existing.id, d);
      ids.push(existing.id);
    } else {
      const opp = await prisma.arbitrageOpportunity.create({
        data: {
          eventId: d.eventId,
          marketType: d.marketType,
          arbType: d.arbType,
          marginPct: d.marginPct,
          detectionReason: d.detectionReason,
          marketRiskScore: d.marketRiskScore,
          dataFreshnessScore: d.dataFreshnessScore,
          executionDifficulty: d.executionDifficulty,
          totalSuggestedStake: d.totalSuggestedStake,
          theoreticalProfit: d.theoreticalProfit,
        },
      });
      await createLegs(opp.id, d);
      ids.push(opp.id);
    }
  }

  return ids;
}

async function createLegs(opportunityId: string, d: DetectedOpportunity) {
  await prisma.arbitrageOpportunityLeg.createMany({
    data: d.legs.map((leg, i) => ({
      opportunityId,
      sportsbookId: leg.sportsbookId,
      outcomeId: leg.outcomeId,
      decimalOdds: leg.decimalOdds,
      impliedProb: leg.impliedProb,
      suggestedStake: leg.suggestedStake,
      sideLabel: leg.sideLabel,
      sortOrder: i,
    })),
  });
}
