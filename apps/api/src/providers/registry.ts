import type { IOddsProvider } from '@arb/shared';
import { TheOddsApiProvider } from './the-odds-api/index.js';

const providers = new Map<string, IOddsProvider>();

export function registerProvider(provider: IOddsProvider): void {
  providers.set(provider.code, provider);
}

export function getProvider(code: string): IOddsProvider | undefined {
  return providers.get(code);
}

export function getEnabledProviders(): IOddsProvider[] {
  return Array.from(providers.values());
}

/** Bootstrap default providers */
export function initProviders(): void {
  registerProvider(new TheOddsApiProvider());
}
