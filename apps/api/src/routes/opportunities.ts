import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { prisma } from '../lib/prisma.js';
import { mapOpportunity } from '../services/opportunities/mapper.js';
import { buildExecutionPlan } from '../services/execution/plan.js';
import { aiService } from '../services/ai/index.js';
import { aiExplainQueue } from '../jobs/queues.js';

const listQuery = z.object({
  status: z.enum(['open', 'stale', 'executed', 'skipped']).optional(),
  minEdgePct: z.coerce.number().optional(),
  marketType: z.string().optional(),
  sportId: z.string().optional(),
  leagueId: z.string().optional(),
});

export async function opportunityRoutes(app: FastifyInstance) {
  app.get('/opportunities', async (req) => {
    const q = listQuery.parse(req.query);
    const opps = await prisma.arbitrageOpportunity.findMany({
      where: {
        status: q.status ?? 'open',
        ...(q.minEdgePct != null
          ? { marginPct: { gte: q.minEdgePct } }
          : {}),
        ...(q.marketType ? { marketType: q.marketType as never } : {}),
        ...(q.leagueId || q.sportId
          ? {
              event: {
                ...(q.leagueId ? { leagueId: q.leagueId } : {}),
                ...(q.sportId ? { sportId: q.sportId } : {}),
              },
            }
          : {}),
      },
      include: {
        legs: { include: { sportsbook: true }, orderBy: { sortOrder: 'asc' } },
        event: { include: { league: { include: { sport: true } } } },
        explanations: { orderBy: { createdAt: 'desc' }, take: 1 },
      },
      orderBy: { marginPct: 'desc' },
      take: 100,
    });
    return { items: opps.map(mapOpportunity) };
  });

  app.get('/opportunities/:id', async (req) => {
    const { id } = req.params as { id: string };
    const opp = await prisma.arbitrageOpportunity.findUnique({
      where: { id },
      include: {
        legs: { include: { sportsbook: true }, orderBy: { sortOrder: 'asc' } },
        event: { include: { league: { include: { sport: true } } } },
        explanations: { orderBy: { createdAt: 'desc' }, take: 1 },
      },
    });
    if (!opp) return { error: 'Not found' };
    const explanation = opp.explanations[0];
    return {
      opportunity: mapOpportunity(opp),
      explanation: explanation
        ? {
            briefText: explanation.briefText,
            detailedText: explanation.detailedText,
            modelName: explanation.modelName,
          }
        : null,
    };
  });

  app.post('/opportunities/:id/explain', async (req) => {
    const { id } = req.params as { id: string };
    await aiExplainQueue.add('explain', { opportunityId: id });
    return { queued: true };
  });

  app.get('/opportunities/:id/execution-plan', async (req) => {
    const { id } = req.params as { id: string };
    const userId = (req.user as { sub?: string } | undefined)?.sub;
    const plan = await buildExecutionPlan(id, userId);
    if (!plan) return { error: 'Not found' };
    return plan;
  });

  app.post('/opportunities/:id/actions', async (req) => {
    const { id } = req.params as { id: string };
    const body = z
      .object({
        actionType: z.enum([
          'viewed',
          'accepted',
          'rejected',
          'executed',
          'partially_executed',
          'skipped',
          'snoozed',
        ]),
        metadata: z.record(z.unknown()).optional(),
        userId: z.string().optional(),
      })
      .parse(req.body);

    const userId =
      (req.user as { sub?: string } | undefined)?.sub ?? body.userId;
    if (!userId) return { error: 'Authentication required' };

    const log = await prisma.userActionLog.create({
      data: {
        userId,
        opportunityId: id,
        actionType: body.actionType,
        metadata: (body.metadata ?? undefined) as Prisma.InputJsonValue | undefined,
      },
    });

    if (body.actionType === 'skipped' || body.actionType === 'rejected') {
      await prisma.arbitrageOpportunity.update({
        where: { id },
        data: { status: 'skipped' },
      });
    }
    if (body.actionType === 'executed') {
      await prisma.arbitrageOpportunity.update({
        where: { id },
        data: { status: 'executed' },
      });
    }

    return { id: log.id };
  });
}
