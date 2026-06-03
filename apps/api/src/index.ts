import 'dotenv/config';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import jwt from '@fastify/jwt';
import { config } from './config.js';
import { initProviders } from './providers/registry.js';
import { authRoutes } from './routes/auth.js';
import { opportunityRoutes } from './routes/opportunities.js';
import { aiRoutes } from './routes/ai.js';
import { metaRoutes } from './routes/meta.js';
import { logger } from './lib/logger.js';

initProviders();

const app = Fastify({ logger: false });

await app.register(cors, { origin: config.CORS_ORIGIN, credentials: true });
await app.register(jwt, { secret: config.JWT_SECRET });

app.decorate(
  'authenticate',
  async (req: { jwtVerify: () => Promise<void> }, reply: { status: (n: number) => { send: (o: object) => void } }) => {
    try {
      await req.jwtVerify();
    } catch {
      reply.status(401).send({ error: 'Unauthorized' });
    }
  },
);

await app.register(metaRoutes);
await app.register(authRoutes);
await app.register(opportunityRoutes);
await app.register(aiRoutes);

app.listen({ port: config.API_PORT, host: config.API_HOST }, (err) => {
  if (err) {
    logger.error(err);
    process.exit(1);
  }
  logger.info(`API listening on ${config.API_HOST}:${config.API_PORT}`);
});
