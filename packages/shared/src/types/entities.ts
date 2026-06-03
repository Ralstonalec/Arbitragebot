export type EventStatus = 'scheduled' | 'live' | 'completed' | 'cancelled' | 'postponed';

export type MarketType =
  | 'moneyline'
  | 'spread'
  | 'total'
  | 'three_way'
  | 'prop_player'
  | 'prop_team'
  | 'other';

export type OutcomeLabel =
  | 'home'
  | 'away'
  | 'draw'
  | 'over'
  | 'under'
  | 'yes'
  | 'no'
  | string;

export type OddsProviderType = 'aggregator' | 'direct_feed' | 'scraper';

export type OpportunityStatus = 'open' | 'stale' | 'executed' | 'skipped';

export type ArbType = 'two_way' | 'three_way' | 'multi_leg' | 'value_edge';

export interface SportsbookDto {
  id: string;
  name: string;
  region: string;
  code: string;
  isOntarioLicensed: boolean;
  metadata?: Record<string, unknown>;
}

export interface OddsProviderDto {
  id: string;
  name: string;
  type: OddsProviderType;
  code: string;
}

export interface SportDto {
  id: string;
  name: string;
  slug: string;
}

export interface LeagueDto {
  id: string;
  sportId: string;
  name: string;
  slug: string;
}

export interface EventDto {
  id: string;
  sportId: string;
  leagueId: string;
  homeTeam: string;
  awayTeam: string;
  startTime: string;
  status: EventStatus;
}

export interface MarketDto {
  id: string;
  eventId: string;
  marketType: MarketType;
  sideCount: number;
  parameters?: Record<string, number | string>;
}

export interface OutcomeDto {
  id: string;
  marketId: string;
  label: OutcomeLabel;
}

export interface QuoteDto {
  id: string;
  outcomeId: string;
  sportsbookId: string;
  providerId: string;
  capturedAt: string;
  decimalOdds: number;
  impliedProb: number;
  isLive: boolean;
  lineVersion?: string;
}
