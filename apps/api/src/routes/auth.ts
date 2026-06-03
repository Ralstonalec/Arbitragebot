import type { FastifyInstance } from 'fastify';
import bcrypt from 'bcryptjs';
import { z } from 'zod';
import { prisma } from '../lib/prisma.js';

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

const loginSchema = registerSchema;

async function requireAuth(req: { jwtVerify: () => Promise<void> }) {
  await req.jwtVerify();
}

export async function authRoutes(app: FastifyInstance) {
  app.post('/auth/register', async (req, reply) => {
    const body = registerSchema.parse(req.body);
    const existing = await prisma.user.findUnique({ where: { email: body.email } });
    if (existing) return reply.status(409).send({ error: 'Email already registered' });

    const passwordHash = await bcrypt.hash(body.password, 12);
    const user = await prisma.user.create({
      data: {
        email: body.email,
        passwordHash,
        settings: { create: {} },
      },
    });

    const token = await reply.jwtSign({ sub: user.id, email: user.email });
    return { token, user: { id: user.id, email: user.email } };
  });

  app.post('/auth/login', async (req, reply) => {
    const body = loginSchema.parse(req.body);
    const user = await prisma.user.findUnique({ where: { email: body.email } });
    if (!user || !(await bcrypt.compare(body.password, user.passwordHash))) {
      return reply.status(401).send({ error: 'Invalid credentials' });
    }
    const token = await reply.jwtSign({ sub: user.id, email: user.email });
    return { token, user: { id: user.id, email: user.email } };
  });

  app.get('/auth/me', { onRequest: [requireAuth] }, async (req) => {
    const payload = req.user as { sub: string; email: string };
    return { id: payload.sub, email: payload.email };
  });
}
