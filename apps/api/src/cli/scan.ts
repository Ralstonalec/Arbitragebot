import 'dotenv/config';
import { initProviders, getProvider } from '../providers/registry.js';
import { ingestProviderOdds } from '../services/ingestion/ingest.js';
import { runArbDetection } from '../services/arbEngine/detect.js';
import { persistOpportunities } from '../services/arbEngine/persist.js';
import { mapOpportunity } from '../services/opportunities/mapper.js';
import { defaultRiskSettings } from '../services/risk/settings.js';
import { prisma } from '../lib/prisma.js';

/**
 * Single ingestion + arb-scan cycle for local debugging.
 * Usage: npm run scan -w @arb/api -- basketball_nba
 */
async function main() {
  const leagueKey = process.argv[2] ?? 'basketball_nba';
  initProviders();

  const provider = await prisma.oddsProvider.findUnique({
    where: { code: 'the_odds_api' },
  });
  const impl = getProvider('the_odds_api');

  if (!provider || !impl) {
    console.error('the_odds_api provider not configured. Run db:seed and set THE_ODDS_API_KEY.');
    process.exit(1);
  }

  console.log(JSON.stringify({ step: 'ingest', leagueKey }));
  const ingest = await ingestProviderOdds(impl, provider.id, leagueKey);
  console.log(JSON.stringify({ step: 'ingest_result', ...ingest }));

  const risk = defaultRiskSettings();
  const detected = await runArbDetection(risk);
  const ids = await persistOpportunities(detected);

  const opps = await prisma.arbitrageOpportunity.findMany({
    where: { id: { in: ids } },
    include: {
      legs: { include: { sportsbook: true } },
      event: { include: { league: { include: { sport: true } } } },
      explanations: { take: 0 },
    },
  });

  console.log(
    JSON.stringify(
      {
        step: 'opportunities',
        count: opps.length,
        items: opps.map(mapOpportunity),
      },
      null,
      2,
    ),
  );
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
