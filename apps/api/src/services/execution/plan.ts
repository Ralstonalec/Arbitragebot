import type { ExecutionPlan } from '@arb/shared';
import { prisma } from '../../lib/prisma.js';
import { loadRiskSettings } from '../risk/settings.js';

const DISCLAIMER =
  'This is an execution assist plan only. You place bets directly with licensed sportsbooks. ' +
  'Theoretical edge does not guarantee profit. Lines may move, bets may be limited or rejected. ' +
  'This platform does not hold funds or access your sportsbook accounts.';

export async function buildExecutionPlan(
  opportunityId: string,
  userId?: string,
): Promise<ExecutionPlan | null> {
  const opp = await prisma.arbitrageOpportunity.findUnique({
    where: { id: opportunityId },
    include: {
      legs: {
        orderBy: { sortOrder: 'asc' },
        include: {
          sportsbook: true,
          outcome: { include: { market: true } },
        },
      },
      event: true,
    },
  });

  if (!opp) return null;

  const settings = await loadRiskSettings(userId);

  return {
    opportunityId: opp.id,
    generatedAt: new Date().toISOString(),
    currency: settings ? 'CAD' : 'CAD',
    totalStake: opp.totalSuggestedStake?.toNumber() ?? 0,
    theoreticalMarginPct: opp.marginPct.toNumber(),
    disclaimer: DISCLAIMER,
    legs: opp.legs.map((leg) => ({
      sportsbookId: leg.sportsbookId,
      sportsbookName: leg.sportsbook.name,
      sportsbookCode: leg.sportsbook.code,
      outcomeLabel: leg.sideLabel,
      marketType: leg.outcome.market.marketType,
      decimalOdds: leg.decimalOdds.toNumber(),
      suggestedStake: leg.suggestedStake.toNumber(),
      selectionIdentifier: `${leg.outcome.market.marketType}:${leg.sideLabel}`,
      deepLinkHint: `/events/${opp.eventId}?book=${leg.sportsbook.code}`,
    })),
  };
}
