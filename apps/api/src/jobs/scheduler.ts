import { ingestQueue, arbScanQueue } from './queues.js';
import { prisma } from '../lib/prisma.js';

const DEFAULT_LEAGUES = ['basketball_nba', 'icehockey_nhl', 'americanfootball_nfl'];

export async function scheduleIngestion(): Promise<void> {
  const providers = await prisma.oddsProvider.findMany({ where: { isEnabled: true } });
  for (const p of providers) {
    for (const leagueKey of DEFAULT_LEAGUES) {
      await ingestQueue.add(
        `ingest-${p.code}-${leagueKey}`,
        { providerCode: p.code, leagueKey },
        { removeOnComplete: 100, removeOnFail: 50 },
      );
    }
  }
}

export async function scheduleArbScan(): Promise<void> {
  await arbScanQueue.add('scan', {}, { removeOnComplete: 50 });
}
