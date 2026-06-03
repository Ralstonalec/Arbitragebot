import type { ProviderEvent, IOddsProvider } from '@arb/shared';
import { MarketType, Prisma } from '@prisma/client';
import { impliedProbabilityFromDecimalOdds } from '../../lib/math/odds.js';
import { logger } from '../../lib/logger.js';
import { prisma } from '../../lib/prisma.js';

export interface IngestResult {
  eventsProcessed: number;
  quotesUpserted: number;
  errors: string[];
}

export async function ingestProviderOdds(
  provider: IOddsProvider,
  providerDbId: string,
  leagueKey: string,
): Promise<IngestResult> {
  const log = logger.child({ provider: provider.code, leagueKey });
  const result: IngestResult = { eventsProcessed: 0, quotesUpserted: 0, errors: [] };

  const mappings = await prisma.sportsbookProviderMapping.findMany({
    where: { oddsProviderId: providerDbId },
    include: { sportsbook: true },
  });
  const bookByExternal = new Map(
    mappings.map((m) => [m.providerBookCode, m.sportsbook]),
  );

  let events: ProviderEvent[];
  try {
    events = await provider.fetchOdds({
      sportKey: leagueKey.split('_')[0] ?? leagueKey,
      leagueKey,
      regions: ['us', 'uk', 'eu'],
      markets: ['h2h', 'spreads', 'totals'],
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    result.errors.push(msg);
    log.error({ err: msg }, 'fetchOdds failed');
    return result;
  }

  for (const pe of events) {
    try {
      const quotes = await upsertEventTree(pe, providerDbId, bookByExternal);
      result.eventsProcessed += 1;
      result.quotesUpserted += quotes;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      result.errors.push(`event ${pe.externalEventId}: ${msg}`);
      log.warn({ externalEventId: pe.externalEventId, err: msg }, 'event ingest failed');
    }
  }

  return result;
}

async function upsertEventTree(
  pe: ProviderEvent,
  providerDbId: string,
  bookByExternal: Map<string, { id: string; name: string; code: string }>,
): Promise<number> {
  let quotesCount = 0;

  const sport = await prisma.sport.findFirst({
    where: { slug: pe.sportKey },
  });
  if (!sport) return 0;

  const league = await prisma.league.findFirst({
    where: { sportId: sport.id, slug: pe.leagueKey },
  });
  if (!league) return 0;

  const extMap = await prisma.externalIdMap.findUnique({
    where: {
      entityType_oddsProviderId_externalKey: {
        entityType: 'event',
        oddsProviderId: providerDbId,
        externalKey: pe.externalEventId,
      },
    },
  });

  let eventId: string;
  if (extMap) {
    eventId = extMap.internalId;
    await prisma.event.update({
      where: { id: eventId },
      data: {
        homeTeam: pe.homeTeam,
        awayTeam: pe.awayTeam,
        startTime: pe.startTime,
        status: mapStatus(pe.status),
      },
    });
  } else {
    const event = await prisma.event.create({
      data: {
        sportId: sport.id,
        leagueId: league.id,
        homeTeam: pe.homeTeam,
        awayTeam: pe.awayTeam,
        startTime: pe.startTime,
      },
    });
    eventId = event.id;
    await prisma.externalIdMap.create({
      data: {
        entityType: 'event',
        internalId: eventId,
        oddsProviderId: providerDbId,
        externalKey: pe.externalEventId,
      },
    });
  }

  for (const pm of pe.markets) {
    const paramsJson = (pm.parameters ?? {}) as Prisma.InputJsonValue;
    const market = await prisma.market.upsert({
      where: {
        eventId_marketType_parameters: {
          eventId,
          marketType: pm.marketType as MarketType,
          parameters: paramsJson,
        },
      },
      create: {
        eventId,
        marketType: pm.marketType as MarketType,
        sideCount: pm.sideCount,
        parameters: paramsJson,
      },
      update: { sideCount: pm.sideCount },
    });

    const bestByOutcomeBook = new Map<string, typeof pm.outcomes[0]>();
    for (const q of pm.outcomes) {
      const key = `${q.outcomeLabel}:${q.sportsbookExternalKey}`;
      const prev = bestByOutcomeBook.get(key);
      if (!prev || q.decimalOdds > prev.decimalOdds) {
        bestByOutcomeBook.set(key, q);
      }
    }

    for (const q of bestByOutcomeBook.values()) {
      const sportsbook = bookByExternal.get(q.sportsbookExternalKey);
      if (!sportsbook) continue;

      const outcome = await prisma.outcome.upsert({
        where: {
          marketId_label: { marketId: market.id, label: String(q.outcomeLabel) },
        },
        create: { marketId: market.id, label: String(q.outcomeLabel) },
        update: {},
      });

      const implied = impliedProbabilityFromDecimalOdds(q.decimalOdds);
      const now = new Date();

      await prisma.quote.upsert({
        where: {
          outcomeId_sportsbookId_providerId: {
            outcomeId: outcome.id,
            sportsbookId: sportsbook.id,
            providerId: providerDbId,
          },
        },
        create: {
          outcomeId: outcome.id,
          sportsbookId: sportsbook.id,
          providerId: providerDbId,
          capturedAt: now,
          decimalOdds: q.decimalOdds,
          impliedProb: implied,
          isLive: q.isLive ?? false,
          lineVersion: q.lineVersion,
        },
        update: {
          capturedAt: now,
          decimalOdds: q.decimalOdds,
          impliedProb: implied,
          isLive: q.isLive ?? false,
          lineVersion: q.lineVersion,
        },
      });

      quotesCount += 1;
    }
  }

  return quotesCount;
}

function mapStatus(status?: string) {
  if (!status) return 'scheduled' as const;
  const s = status.toLowerCase();
  if (s.includes('live')) return 'live' as const;
  if (s.includes('complete')) return 'completed' as const;
  if (s.includes('cancel')) return 'cancelled' as const;
  return 'scheduled' as const;
}
