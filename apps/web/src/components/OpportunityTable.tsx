'use client';

import type { ArbitrageOpportunityDto } from '@arb/shared';
import Link from 'next/link';

function minutesToStart(iso: string): number {
  return Math.round((new Date(iso).getTime() - Date.now()) / 60000);
}

export function OpportunityTable({ items }: { items: ArbitrageOpportunityDto[] }) {
  if (items.length === 0) {
    return (
      <div className="card">
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          No open opportunities. Run ingestion + scan (see README) or wait for the job queue.
        </p>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table>
        <thead>
          <tr>
            <th>Event</th>
            <th>Market</th>
            <th>Edge</th>
            <th>Books</th>
            <th>Starts in</th>
            <th>Freshness</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((o) => {
            const mins = o.event ? minutesToStart(o.event.startTime) : null;
            const books = [...new Set(o.legs.map((l) => l.sportsbookName))].join(', ');
            return (
              <tr key={o.id}>
                <td>
                  <div>{o.event?.awayTeam} @ {o.event?.homeTeam}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                    {o.event?.sportName} · {o.event?.leagueName}
                  </div>
                </td>
                <td>{o.marketType}</td>
                <td>
                  <span className="badge badge-edge">{o.marginPct.toFixed(2)}%</span>
                </td>
                <td style={{ fontSize: '0.85rem' }}>{books}</td>
                <td>{mins != null ? `${mins}m` : '—'}</td>
                <td>
                  <span className={o.dataFreshnessScore < 50 ? 'badge badge-warn' : 'badge badge-edge'}>
                    {o.dataFreshnessScore}
                  </span>
                </td>
                <td>
                  <Link href={`/opportunities/${o.id}`}>Details →</Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
