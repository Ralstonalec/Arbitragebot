import 'dotenv/config';
import { Worker } from 'bullmq';
import { config } from '../config.js';
import { initProviders, getProvider } from '../providers/registry.js';
import { ingestProviderOdds } from '../services/ingestion/ingest.js';
import { runArbDetection } from '../services/arbEngine/detect.js';
import { persistOpportunities } from '../services/arbEngine/persist.js';
import { aiService } from '../services/ai/index.js';
import { mapOpportunity } from '../services/opportunities/mapper.js';
import { prisma } from '../lib/prisma.js';
import { logger } from '../lib/logger.js';
import { defaultRiskSettings } from '../services/risk/settings.js';

initProviders();

const connection = { url: config.REDIS_URL };

new Worker(
  'odds-ingest',
  async (job) => {
    const { providerCode, leagueKey } = job.data as {
      providerCode: string;
      leagueKey: string;
    };
    const provider = getProvider(providerCode);
    const dbProvider = await prisma.oddsProvider.findUnique({
      where: { code: providerCode },
    });
    if (!provider || !dbProvider) throw new Error(`Provider ${providerCode} not found`);
    const start = Date.now();
    const result = await ingestProviderOdds(provider, dbProvider.id, leagueKey);
    logger.info(
      { ...result, latencyMs: Date.now() - start, providerCode, leagueKey },
      'ingest job complete',
    );
    return result;
  },
  { connection },
);

new Worker(
  'arb-scan',
  async () => {
    const start = Date.now();
    const detected = await runArbDetection(defaultRiskSettings());
    const ids = await persistOpportunities(detected);
    logger.info(
      { count: detected.length, persisted: ids.length, latencyMs: Date.now() - start },
      'arb scan complete',
    );
    return { found: detected.length, ids };
  },
  { connection },
);

new Worker(
  'ai-explain',
  async (job) => {
    const { opportunityId } = job.data as { opportunityId: string };
    const opp = await prisma.arbitrageOpportunity.findUnique({
      where: { id: opportunityId },
      include: {
        legs: { include: { sportsbook: true } },
        event: { include: { league: { include: { sport: true } } } },
        explanations: { take: 0 },
      },
    });
    if (!opp) return;
    const dto = mapOpportunity(opp);
    const explanation = await aiService.explainOpportunity({ opportunity: dto });
    await prisma.aiExplanation.create({
      data: {
        opportunityId,
        briefText: explanation.briefText,
        detailedText: explanation.detailedText,
        modelName: explanation.modelName,
      },
    });
  },
  { connection },
);

logger.info('BullMQ workers started');
