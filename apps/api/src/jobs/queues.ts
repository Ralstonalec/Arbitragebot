import { Queue } from 'bullmq';
import { config } from '../config.js';

const connection = { url: config.REDIS_URL };

export const ingestQueue = new Queue('odds-ingest', { connection });
export const arbScanQueue = new Queue('arb-scan', { connection });
export const aiExplainQueue = new Queue('ai-explain', { connection });
