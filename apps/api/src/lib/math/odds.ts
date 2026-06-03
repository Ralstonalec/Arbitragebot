/**
 * Core odds / arbitrage math helpers.
 * All stake sizing assumes decimal odds and mutually exclusive outcomes.
 */

/** Implied probability from decimal odds: 1 / odds */
export function impliedProbabilityFromDecimalOdds(decimalOdds: number): number {
  if (decimalOdds <= 1) return 1;
  return 1 / decimalOdds;
}

/** Sum of implied probs < 1 indicates theoretical arb (before vig removal) */
export function isTwoWayArb(oddsA: number, oddsB: number): boolean {
  const sum =
    impliedProbabilityFromDecimalOdds(oddsA) + impliedProbabilityFromDecimalOdds(oddsB);
  return sum < 1;
}

export function isThreeWayArb(oddsA: number, oddsB: number, oddsC: number): boolean {
  const sum =
    impliedProbabilityFromDecimalOdds(oddsA) +
    impliedProbabilityFromDecimalOdds(oddsB) +
    impliedProbabilityFromDecimalOdds(oddsC);
  return sum < 1;
}

/** Arb margin as % of total stake returned if all legs fill at quoted odds */
export function arbMarginPct(...decimalOdds: number[]): number {
  const sum = decimalOdds.reduce(
    (acc, o) => acc + impliedProbabilityFromDecimalOdds(o),
    0,
  );
  if (sum >= 1) return 0;
  return ((1 - sum) / sum) * 100;
}

/**
 * Equal-profit stake allocation for 2-way arb.
 * totalStake is the sum across both legs; returns [stakeA, stakeB].
 */
export function computeTwoWayArbStakes(
  oddsA: number,
  oddsB: number,
  totalStake: number,
): [number, number] {
  const invA = 1 / oddsA;
  const invB = 1 / oddsB;
  const sumInv = invA + invB;
  const stakeA = (totalStake * invA) / sumInv;
  const stakeB = (totalStake * invB) / sumInv;
  return [roundStake(stakeA), roundStake(stakeB)];
}

/** Equal-profit stake allocation for 3-way (e.g. soccer 1X2) */
export function computeThreeWayArbStakes(
  oddsA: number,
  oddsB: number,
  oddsC: number,
  totalStake: number,
): [number, number, number] {
  const invA = 1 / oddsA;
  const invB = 1 / oddsB;
  const invC = 1 / oddsC;
  const sumInv = invA + invB + invC;
  return [
    roundStake((totalStake * invA) / sumInv),
    roundStake((totalStake * invB) / sumInv),
    roundStake((totalStake * invC) / sumInv),
  ];
}

/** Capped Kelly stake for value (non-guaranteed) spots */
export function cappedKellyStake(
  bankroll: number,
  decimalOdds: number,
  estimatedEdge: number,
  kellyCap: number,
  maxBetPct: number,
): number {
  const b = decimalOdds - 1;
  const p = impliedProbabilityFromDecimalOdds(decimalOdds) + estimatedEdge;
  const q = 1 - p;
  const kelly = (b * p - q) / b;
  const fraction = Math.max(0, Math.min(kelly * kellyCap, maxBetPct / 100));
  return roundStake(bankroll * fraction);
}

function roundStake(n: number): number {
  return Math.round(n * 100) / 100;
}
