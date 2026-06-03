import type { MarketType, OutcomeLabel } from './entities.js';

/** Normalized payload returned by any odds provider adapter */
export interface ProviderSportsbook {
  externalKey: string;
  name: string;
  region?: string;
}

export interface ProviderSportLeague {
  sportKey: string;
  sportTitle: string;
  leagueKey: string;
  leagueTitle: string;
}

export interface ProviderOutcomeQuote {
  outcomeLabel: OutcomeLabel;
  decimalOdds: number;
  sportsbookExternalKey: string;
  isLive?: boolean;
  lineVersion?: string;
}

export interface ProviderMarket {
  marketType: MarketType;
  sideCount: number;
  parameters?: Record<string, number | string>;
  outcomes: ProviderOutcomeQuote[];
}

export interface ProviderEvent {
  externalEventId: string;
  sportKey: string;
  leagueKey: string;
  homeTeam: string;
  awayTeam: string;
  startTime: Date;
  status?: string;
  markets: ProviderMarket[];
}

export interface FetchOddsParams {
  sportKey: string;
  leagueKey?: string;
  /** ISO window start */
  commenceTimeFrom?: Date;
  /** ISO window end */
  commenceTimeTo?: Date;
  regions?: string[];
  markets?: string[];
}

export interface IOddsProvider {
  readonly code: string;
  readonly name: string;

  listSportsbooks(): Promise<ProviderSportsbook[]>;
  listSportsAndLeagues(): Promise<ProviderSportLeague[]>;
  fetchOdds(params: FetchOddsParams): Promise<ProviderEvent[]>;
}
