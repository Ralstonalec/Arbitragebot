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

export type OpportunityStatus = 'open' | 'stale' | 'executed' | 'skipped';

export type ArbType = 'two_way' | 'three_way' | 'multi_leg' | 'value_edge';
