import { prisma } from '../../lib/prisma.js';

export interface RiskSettings {
  defaultBankroll: number;
  maxRiskPerBetPct: number;
  maxDailyLossPct: number;
  minArbEdgePct: number;
  minTimeToStartMinutes: number;
  leaguesWhitelist: string[];
  sportsbooksWhitelist: string[];
  kellyFractionCap: number;
}

export async function loadRiskSettings(userId?: string): Promise<RiskSettings> {
  if (!userId) {
    return defaultRiskSettings();
  }
  const s = await prisma.userSettings.findUnique({ where: { userId } });
  if (!s) return defaultRiskSettings();
  return {
    defaultBankroll: s.defaultBankroll.toNumber(),
    maxRiskPerBetPct: s.maxRiskPerBetPct.toNumber(),
    maxDailyLossPct: s.maxDailyLossPct.toNumber(),
    minArbEdgePct: s.minArbEdgePct.toNumber(),
    minTimeToStartMinutes: s.minTimeToStartMinutes,
    leaguesWhitelist: s.leaguesWhitelist,
    sportsbooksWhitelist: s.sportsbooksWhitelist,
    kellyFractionCap: s.kellyFractionCap.toNumber(),
  };
}

export function defaultRiskSettings(): RiskSettings {
  return {
    defaultBankroll: 2000,
    maxRiskPerBetPct: 2,
    maxDailyLossPct: 5,
    minArbEdgePct: 0.5,
    minTimeToStartMinutes: 15,
    leaguesWhitelist: [],
    sportsbooksWhitelist: [],
    kellyFractionCap: 0.25,
  };
}
