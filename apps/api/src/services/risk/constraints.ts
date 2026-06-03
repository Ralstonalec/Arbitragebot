import type { RiskSettings } from './settings.js';

/** Clamp total arb stake to bankroll rules */
export function applyRiskConstraints(
  proposedTotalStake: number,
  bankroll: number,
  risk?: RiskSettings,
): number {
  const maxPct = risk?.maxRiskPerBetPct ?? 2;
  const cap = bankroll * (maxPct / 100);
  return Math.min(proposedTotalStake, cap, bankroll);
}
