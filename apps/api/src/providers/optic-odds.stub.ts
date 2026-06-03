import type { FetchOddsParams } from '@arb/shared';
import { BaseOddsProvider } from './base.js';

/**
 * Placeholder for OpticOdds — implement when API credentials are available.
 * Maps provider JSON into the same ProviderEvent schema as TheOddsApiProvider.
 */
export class OpticOddsProvider extends BaseOddsProvider {
  readonly code = 'optic_odds';
  readonly name = 'OpticOdds';

  async listSportsbooks() {
    return [];
  }

  async listSportsAndLeagues(): Promise<never> {
    throw new Error('OpticOddsProvider not implemented — add API adapter');
  }

  async fetchOdds(_params: FetchOddsParams): Promise<never> {
    throw new Error('OpticOddsProvider not implemented — add API adapter');
  }
}
