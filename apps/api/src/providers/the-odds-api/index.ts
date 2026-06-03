import type { FetchOddsParams, ProviderSportsbook } from '@arb/shared';
import { config } from '../../config.js';
import { providerLogger } from '../../lib/logger.js';
import { BaseOddsProvider } from '../base.js';
import { mapSportToLeague, mapTheOddsApiEvent } from './mapper.js';
import type { TheOddsApiEvent, TheOddsApiSport } from './types.js';

const log = providerLogger('the_odds_api', 'fetch');

export class TheOddsApiProvider extends BaseOddsProvider {
  readonly code = 'the_odds_api';
  readonly name = 'The Odds API';

  private get apiKey(): string {
    const key = config.THE_ODDS_API_KEY;
    if (!key) throw new Error('THE_ODDS_API_KEY is not configured');
    return key;
  }

  private url(path: string, params?: Record<string, string>): string {
    const base = config.THE_ODDS_API_BASE_URL.replace(/\/$/, '');
    const u = new URL(`${base}${path}`);
    u.searchParams.set('apiKey', this.apiKey);
    if (params) {
      for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
    }
    return u.toString();
  }

  async listSportsbooks(): Promise<ProviderSportsbook[]> {
    // The Odds API does not expose a dedicated books list; books appear per event.
    return [];
  }

  async listSportsAndLeagues() {
    const res = await this.fetchWithRetry(this.url('/sports'), { method: 'GET' });
    if (!res.ok) {
      const body = await res.text();
      log.error({ status: res.status, body }, 'listSports failed');
      throw new Error(`The Odds API /sports failed: ${res.status}`);
    }
    const sports = (await res.json()) as TheOddsApiSport[];
    return sports.filter((s) => s.active).map(mapSportToLeague);
  }

  async fetchOdds(params: FetchOddsParams) {
    const leagueKey = params.leagueKey ?? params.sportKey;
    const regions = (params.regions ?? ['us', 'uk', 'eu']).join(',');
    const markets = (params.markets ?? ['h2h', 'spreads', 'totals']).join(',');

    const query: Record<string, string> = {
      regions,
      markets,
      oddsFormat: 'decimal',
      dateFormat: 'iso',
    };

    const res = await this.fetchWithRetry(
      this.url(`/sports/${leagueKey}/odds`, query),
      { method: 'GET' },
    );

    if (!res.ok) {
      const body = await res.text();
      log.error({ status: res.status, leagueKey, body }, 'fetchOdds failed');
      throw new Error(`The Odds API odds failed: ${res.status}`);
    }

    const events = (await res.json()) as TheOddsApiEvent[];
    log.info({ leagueKey, eventCount: events.length }, 'fetched odds');

    let filtered = events;
    if (params.commenceTimeFrom) {
      filtered = filtered.filter(
        (e) => new Date(e.commence_time) >= params.commenceTimeFrom!,
      );
    }
    if (params.commenceTimeTo) {
      filtered = filtered.filter(
        (e) => new Date(e.commence_time) <= params.commenceTimeTo!,
      );
    }

    return filtered.map(mapTheOddsApiEvent);
  }
}
