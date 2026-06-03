'use client';

export interface FilterState {
  minEdgePct: string;
  marketType: string;
}

export function OpportunityFilters({
  filters,
  onChange,
}: {
  filters: FilterState;
  onChange: (f: FilterState) => void;
}) {
  return (
    <div className="card" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'end' }}>
      <label>
        <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Min edge %</div>
        <input
          type="number"
          step="0.1"
          value={filters.minEdgePct}
          onChange={(e) => onChange({ ...filters, minEdgePct: e.target.value })}
        />
      </label>
      <label>
        <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Market type</div>
        <select
          value={filters.marketType}
          onChange={(e) => onChange({ ...filters, marketType: e.target.value })}
        >
          <option value="">All</option>
          <option value="moneyline">Moneyline</option>
          <option value="spread">Spread</option>
          <option value="total">Total</option>
          <option value="three_way">Three-way</option>
        </select>
      </label>
    </div>
  );
}
