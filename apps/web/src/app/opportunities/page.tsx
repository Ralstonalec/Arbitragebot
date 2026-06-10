'use client';

import { useCallback, useEffect, useState } from 'react';
import type { ArbitrageOpportunityDto } from '@/types';
import { fetchOpportunities } from '@/lib/api';
import { OpportunityFilters, type FilterState } from '@/components/OpportunityFilters';
import { OpportunityTable } from '@/components/OpportunityTable';

export default function OpportunitiesPage() {
  const [filters, setFilters] = useState<FilterState>({ minEdgePct: '0', marketType: '' });
  const [items, setItems] = useState<ArbitrageOpportunityDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities({
        minEdgePct: filters.minEdgePct ? Number(filters.minEdgePct) : undefined,
        marketType: filters.marketType || undefined,
        status: 'open',
      });
      setItems(data);
    } catch {
      setError('Could not reach API. Is the backend running on port 3001?');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="container">
      <h1 style={{ marginTop: 0 }}>Theoretical arbitrage & edge</h1>
      <p className="disclaimer">
        Listed edges are <strong>theoretical</strong> based on quoted odds at capture time.
        Execution risk includes line moves, limits, and partial fills. This tool assists research only.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
        <OpportunityFilters filters={filters} onChange={setFilters} />
        <button type="button" onClick={load} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && <OpportunityTable items={items} />}
    </div>
  );
}
