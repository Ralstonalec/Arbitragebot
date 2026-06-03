import { ArbType, MarketType } from '@prisma/client';
import {
  arbMarginPct,
  computeThreeWayArbStakes,
  computeTwoWayArbStakes,
  impliedProbabilityFromDecimalOdds,
  isThreeWayArb,
  isTwoWayArb,
} from '../../lib/math/odds.js';
import { prisma } from '../../lib/prisma.js';
import type { RiskSettings } from '../risk/settings.js';
import { applyRiskConstraints } from '../risk/constraints.js';

export interface DetectedOpportunity {
  eventId: string;
  marketType: MarketType;
  arbType: ArbType;
  marginPct: number;
  detectionReason: string;
  marketRiskScore: number;
  dataFreshnessScore: number;
  executionDifficulty: number;
  legs: Array<{
    sportsbookId: string;
    outcomeId: string;
    decimalOdds: number;
    impliedProb: number;
    suggestedStake: number;
    sideLabel: string;
  }>;
  totalSuggestedStake: number;
  theoreticalProfit: number;
}

const TWO_WAY_TYPES: MarketType[] = ['moneyline', 'spread', 'total'];
const THREE_WAY_TYPE: MarketType = 'three_way';

export async function runArbDetection(
  risk?: RiskSettings,
): Promise<DetectedOpportunity[]> {
  const opportunities: DetectedOpportunity[] = [];
  const minEdge = risk?.minArbEdgePct ?? 0.5;

  const events = await prisma.event.findMany({
    where: {
      status: { in: ['scheduled', 'live'] },
      startTime: { gt: new Date() },
    },
    include: {
      markets: {
        include: {
          outcomes: {
            include: {
              quotes: {
                include: { sportsbook: true },
                orderBy: { capturedAt: 'desc' },
              },
            },
          },
        },
      },
      league: { include: { sport: true } },
    },
    take: 200,
  });

  for (const event of events) {
    if (risk?.minTimeToStartMinutes) {
      const mins =
        (event.startTime.getTime() - Date.now()) / 60000;
      if (mins < risk.minTimeToStartMinutes) continue;
    }

    for (const market of event.markets) {
      if (TWO_WAY_TYPES.includes(market.marketType) && market.outcomes.length >= 2) {
        const detected = detectTwoWayMarket(market, event.id, minEdge, risk);
        if (detected) opportunities.push(detected);
      }
      if (market.marketType === THREE_WAY_TYPE && market.outcomes.length >= 3) {
        const detected = detectThreeWayMarket(market, event.id, minEdge, risk);
        if (detected) opportunities.push(detected);
      }
    }
  }

  return opportunities;
}

type MarketWithQuotes = {
  id: string;
  marketType: MarketType;
  outcomes: Array<{
    id: string;
    label: string;
    quotes: Array<{
      decimalOdds: { toNumber(): number };
      impliedProb: { toNumber(): number };
      capturedAt: Date;
      sportsbookId: string;
      sportsbook: { name: string };
    }>;
  }>;
};

function detectTwoWayMarket(
  market: MarketWithQuotes,
  eventId: string,
  minEdgePct: number,
  risk?: RiskSettings,
): DetectedOpportunity | null {
  const sides = market.outcomes.slice(0, 2);
  if (sides.length < 2) return null;

  const best: Array<{
    outcomeId: string;
    label: string;
    sportsbookId: string;
    sportsbookName: string;
    decimalOdds: number;
    impliedProb: number;
    capturedAt: Date;
  }> = [];

  for (const side of sides) {
    const top = side.quotes[0];
    if (!top) return null;
    best.push({
      outcomeId: side.id,
      label: side.label,
      sportsbookId: top.sportsbookId,
      sportsbookName: top.sportsbook.name,
      decimalOdds: top.decimalOdds.toNumber(),
      impliedProb: top.impliedProb.toNumber(),
      capturedAt: top.capturedAt,
    });
  }

  if (!isTwoWayArb(best[0].decimalOdds, best[1].decimalOdds)) return null;

  const margin = arbMarginPct(best[0].decimalOdds, best[1].decimalOdds);
  if (margin < minEdgePct) return null;

  const bankroll = risk?.defaultBankroll ?? 2000;
  const maxPct = risk?.maxRiskPerBetPct ?? 2;
  let totalStake = Math.min(bankroll * (maxPct / 100), bankroll * 0.05);
  totalStake = applyRiskConstraints(totalStake, bankroll, risk);

  const [stake0, stake1] = computeTwoWayArbStakes(
    best[0].decimalOdds,
    best[1].decimalOdds,
    totalStake,
  );

  const freshness = freshnessScore(best.map((b) => b.capturedAt));
  const profit = totalStake * (margin / 100);

  return {
    eventId,
    marketType: market.marketType,
    arbType: 'two_way',
    marginPct: margin,
    detectionReason: `Sum of implied probabilities < 1 across ${best[0].sportsbookName} and ${best[1].sportsbookName}`,
    marketRiskScore: heuristicMarketRisk(market.marketType),
    dataFreshnessScore: freshness,
    executionDifficulty: best[0].sportsbookId === best[1].sportsbookId ? 80 : 40,
    legs: [
      {
        sportsbookId: best[0].sportsbookId,
        outcomeId: best[0].outcomeId,
        decimalOdds: best[0].decimalOdds,
        impliedProb: best[0].impliedProb,
        suggestedStake: stake0,
        sideLabel: best[0].label,
      },
      {
        sportsbookId: best[1].sportsbookId,
        outcomeId: best[1].outcomeId,
        decimalOdds: best[1].decimalOdds,
        impliedProb: best[1].impliedProb,
        suggestedStake: stake1,
        sideLabel: best[1].label,
      },
    ],
    totalSuggestedStake: stake0 + stake1,
    theoreticalProfit: profit,
  };
}

function detectThreeWayMarket(
  market: MarketWithQuotes,
  eventId: string,
  minEdgePct: number,
  risk?: RiskSettings,
): DetectedOpportunity | null {
  type BestLeg = {
    outcomeId: string;
    label: string;
    sportsbookId: string;
    decimalOdds: number;
    impliedProb: number;
    capturedAt: Date;
  };

  const labels = ['home', 'draw', 'away'];
  const best: BestLeg[] = [];
  for (const label of labels) {
    const side = market.outcomes.find((o) => o.label === label);
    const top = side?.quotes[0];
    if (!side || !top) return null;
    best.push({
      outcomeId: side.id,
      label: side.label,
      sportsbookId: top.sportsbookId,
      decimalOdds: top.decimalOdds.toNumber(),
      impliedProb: top.impliedProb.toNumber(),
      capturedAt: top.capturedAt,
    });
  }

  const [a, b, c] = best;

  if (!isThreeWayArb(a.decimalOdds, b.decimalOdds, c.decimalOdds)) return null;

  const margin = arbMarginPct(a.decimalOdds, b.decimalOdds, c.decimalOdds);
  if (margin < minEdgePct) return null;

  const bankroll = risk?.defaultBankroll ?? 2000;
  const maxPct = risk?.maxRiskPerBetPct ?? 2;
  let totalStake = Math.min(bankroll * (maxPct / 100), bankroll * 0.05);
  totalStake = applyRiskConstraints(totalStake, bankroll, risk);

  const [s0, s1, s2] = computeThreeWayArbStakes(
    a.decimalOdds,
    b.decimalOdds,
    c.decimalOdds,
    totalStake,
  );

  const uniqueBooks = new Set([a.sportsbookId, b.sportsbookId, c.sportsbookId]);

  return {
    eventId,
    marketType: 'three_way',
    arbType: 'three_way',
    marginPct: margin,
    detectionReason: 'Three-way 1X2 implied probability sum below 1',
    marketRiskScore: 55,
    dataFreshnessScore: freshnessScore([a.capturedAt, b.capturedAt, c.capturedAt]),
    executionDifficulty: uniqueBooks.size === 3 ? 35 : 55,
    legs: [
      { ...a, suggestedStake: s0, sideLabel: a.label },
      { ...b, suggestedStake: s1, sideLabel: b.label },
      { ...c, suggestedStake: s2, sideLabel: c.label },
    ],
    totalSuggestedStake: s0 + s1 + s2,
    theoreticalProfit: totalStake * (margin / 100),
  };
}

function freshnessScore(dates: Date[]): number {
  const ageSec = Math.max(...dates.map((d) => (Date.now() - d.getTime()) / 1000));
  if (ageSec < 30) return 95;
  if (ageSec < 120) return 75;
  if (ageSec < 300) return 50;
  return 25;
}

function heuristicMarketRisk(marketType: MarketType): number {
  switch (marketType) {
    case 'moneyline':
      return 30;
    case 'spread':
    case 'total':
      return 45;
    default:
      return 60;
  }
}
