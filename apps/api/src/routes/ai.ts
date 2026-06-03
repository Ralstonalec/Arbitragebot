import type { FastifyInstance } from 'fastify';
import { aiService } from '../services/ai/index.js';
import type {
  ExplainOpportunityRequest,
  NormalizeEntitiesRequest,
  StrategyReviewRequest,
} from '@arb/shared';

export async function aiRoutes(app: FastifyInstance) {
  app.post('/ai/explain-opportunity', async (req) => {
    const body = req.body as ExplainOpportunityRequest;
    return aiService.explainOpportunity(body);
  });

  app.post('/ai/normalize-entities', async (req) => {
    const body = req.body as NormalizeEntitiesRequest;
    return aiService.normalizeEntities(body);
  });

  app.post('/ai/strategy-review', async (req) => {
    const body = req.body as StrategyReviewRequest;
    return aiService.strategyReview(body);
  });
}
