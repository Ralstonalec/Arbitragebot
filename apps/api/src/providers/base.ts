import type { FetchOddsParams, IOddsProvider } from '@arb/shared';

export abstract class BaseOddsProvider implements IOddsProvider {
  abstract readonly code: string;
  abstract readonly name: string;

  abstract listSportsbooks(): ReturnType<IOddsProvider['listSportsbooks']>;
  abstract listSportsAndLeagues(): ReturnType<IOddsProvider['listSportsAndLeagues']>;
  abstract fetchOdds(params: FetchOddsParams): ReturnType<IOddsProvider['fetchOdds']>;

  protected async fetchWithRetry(
    url: string,
    init: RequestInit,
    opts: { maxRetries?: number; retryDelayMs?: number } = {},
  ): Promise<Response> {
    const maxRetries = opts.maxRetries ?? 3;
    const retryDelayMs = opts.retryDelayMs ?? 1000;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const res = await fetch(url, init);
        if (res.status === 429) {
          const retryAfter = Number(res.headers.get('retry-after') ?? '5');
          await sleep(retryAfter * 1000);
          continue;
        }
        return res;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (attempt < maxRetries) await sleep(retryDelayMs * (attempt + 1));
      }
    }
    throw lastError ?? new Error('fetch failed');
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
