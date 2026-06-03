import type { MarketType, OutcomeLabel } from '@arb/shared';
import type {
  ProviderEvent,
  ProviderMarket,
  ProviderOutcomeQuote,
  ProviderSportLeague,
} from '@arb/shared';
import type { TheOddsApiEvent, TheOddsApiMarket, TheOddsApiSport } from './types.js';

const MARKET_KEY_MAP: Record<string, MarketType> = {
  h2h: 'moneyline',
  spreads: 'spread',
  totals: 'total',
};

export function mapSportToLeague(sport: TheOddsApiSport): ProviderSportLeague {
  return {
    sportKey: sport.key.split('_')[0] ?? sport.key,
    sportTitle: sport.group,
    leagueKey: sport.key,
    leagueTitle: sport.title,
  };
}

export function mapTheOddsApiEvent(raw: TheOddsApiEvent): ProviderEvent {
  const marketMap = new Map<string, ProviderMarket>();

  for (const bookmaker of raw.bookmakers) {
    for (const mkt of bookmaker.markets) {
      const marketType = MARKET_KEY_MAP[mkt.key] ?? 'other';
      const key = `${marketType}:${JSON.stringify(extractParams(mkt))}`;
      let market = marketMap.get(key);
      if (!market) {
        market = {
          marketType,
          sideCount: mkt.outcomes.length,
          parameters: extractParams(mkt),
          outcomes: [],
        };
        marketMap.set(key, market);
      }
      for (const out of mkt.outcomes) {
        const label = mapOutcomeLabel(out.name, raw.home_team, raw.away_team, marketType);
        const existing = market.outcomes.find(
          (o) =>
            o.outcomeLabel === label &&
            o.sportsbookExternalKey === bookmaker.key,
        );
        if (!existing || out.price > (existing?.decimalOdds ?? 0)) {
          if (existing) {
            existing.decimalOdds = out.price;
          } else {
            market.outcomes.push({
              outcomeLabel: label,
              decimalOdds: out.price,
              sportsbookExternalKey: bookmaker.key,
              lineVersion: mkt.last_update ?? bookmaker.last_update,
            });
          }
        }
      }
    }
  }

  const [sportKey, ...rest] = raw.sport_key.split('_');
  const leagueKey = raw.sport_key;

  return {
    externalEventId: raw.id,
    sportKey: sportKey ?? raw.sport_key,
    leagueKey,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    startTime: new Date(raw.commence_time),
    markets: Array.from(marketMap.values()),
  };
}

function extractParams(mkt: TheOddsApiMarket): Record<string, number | string> | undefined {
  const point = mkt.outcomes.find((o) => o.point != null)?.point;
  if (point == null) return undefined;
  return { line: point };
}

function mapOutcomeLabel(
  name: string,
  home: string,
  away: string,
  marketType: MarketType,
): OutcomeLabel {
  if (name === home) return 'home';
  if (name === away) return 'away';
  if (name.toLowerCase() === 'draw') return 'draw';
  if (name.toLowerCase() === 'over') return 'over';
  if (name.toLowerCase() === 'under') return 'under';
  return name.toLowerCase().replace(/\s+/g, '_');
}
