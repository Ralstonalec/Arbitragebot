import 'dotenv/config';
import { z } from 'zod';

const envSchema = z.object({
  DATABASE_URL: z.string().min(1),
  REDIS_URL: z.string().default('redis://localhost:6379'),
  API_PORT: z.coerce.number().default(3001),
  API_HOST: z.string().default('0.0.0.0'),
  JWT_SECRET: z.string().default('dev-secret-change-me-in-production'),
  CORS_ORIGIN: z.string().default('http://localhost:3000'),
  THE_ODDS_API_KEY: z.string().optional(),
  THE_ODDS_API_BASE_URL: z
    .string()
    .default('https://api.the-odds-api.com/v4'),
  OPENAI_API_KEY: z.string().optional(),
  AI_MODEL: z.string().default('gpt-4o-mini'),
});

export const config = envSchema.parse(process.env);
