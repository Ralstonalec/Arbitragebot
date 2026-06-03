import type { FastifyInstance } from 'fastify';
import { prisma } from '../lib/prisma.js';

export async function metaRoutes(app: FastifyInstance) {
  app.get('/health', async () => ({ status: 'ok', timestamp: new Date().toISOString() }));

  app.get('/sports', async () => {
    const sports = await prisma.sport.findMany({
      include: { leagues: true },
    });
    return { items: sports };
  });

  app.get('/sportsbooks', async () => {
    const books = await prisma.sportsbook.findMany({ orderBy: { name: 'asc' } });
    return {
      items: books.map((b) => ({
        id: b.id,
        name: b.name,
        code: b.code,
        region: b.region,
        isOntarioLicensed: b.isOntarioLicensed,
      })),
    };
  });
}
