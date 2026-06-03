'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import type { ArbitrageOpportunityDto, ExecutionPlan } from '@arb/shared';
import {
  fetchOpportunity,
  fetchExecutionPlan,
  postOpportunityAction,
  queueExplanation,
} from '@/lib/api';

export default function OpportunityDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [opp, setOpp] = useState<ArbitrageOpportunityDto | null>(null);
  const [explanation, setExplanation] = useState<{
    briefText: string;
    detailedText: string;
    modelName: string;
  } | null>(null);
  const [plan, setPlan] = useState<ExecutionPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOpportunity(id)
      .then((data) => {
        setOpp(data.opportunity);
        setExplanation(data.explanation);
      })
      .catch(() => setError('Failed to load opportunity'));
    fetchExecutionPlan(id).then(setPlan).catch(() => undefined);
  }, [id]);

  async function action(actionType: string) {
    await postOpportunityAction(id, actionType);
    if (actionType === 'skipped' || actionType === 'rejected') {
      window.location.href = '/';
    }
  }

  if (error) return <div className="container"><p style={{ color: 'var(--danger)' }}>{error}</p></div>;
  if (!opp) return <div className="container"><p>Loading…</p></div>;

  return (
    <div className="container">
      <p><Link href="/">← Back to list</Link></p>
      <h1>
        {opp.event?.awayTeam} @ {opp.event?.homeTeam}
      </h1>
      <p style={{ color: 'var(--muted)' }}>
        {opp.event?.sportName} · {opp.event?.leagueName} · starts{' '}
        {opp.event ? new Date(opp.event.startTime).toLocaleString() : ''}
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
        <span className="badge badge-edge">Edge {opp.marginPct.toFixed(2)}%</span>
        <span className="badge">{opp.arbType}</span>
        <span className="badge">Freshness {opp.dataFreshnessScore}</span>
        <span className="badge">Exec difficulty {opp.executionDifficulty}</span>
      </div>

      <p className="disclaimer">{opp.detectionReason}</p>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <h2>Legs & suggested stakes</h2>
        <table>
          <thead>
            <tr>
              <th>Book</th>
              <th>Selection</th>
              <th>Odds</th>
              <th>Stake (CAD)</th>
            </tr>
          </thead>
          <tbody>
            {opp.legs.map((leg) => (
              <tr key={leg.outcomeId}>
                <td>{leg.sportsbookName}</td>
                <td>{leg.sideLabel}</td>
                <td>{leg.decimalOdds.toFixed(3)}</td>
                <td>{leg.suggestedStake.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {opp.theoreticalProfit != null && (
          <p style={{ marginTop: '0.75rem' }}>
            Theoretical profit if all legs fill at quoted odds:{' '}
            <strong>${opp.theoreticalProfit.toFixed(2)}</strong> (not guaranteed)
          </p>
        )}
      </section>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Explanation</h2>
          <button type="button" onClick={() => queueExplanation(id)}>
            Regenerate
          </button>
        </div>
        {explanation ? (
          <>
            <p>{explanation.briefText}</p>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: 'var(--muted)' }}>
              {explanation.detailedText}
            </pre>
            <p style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Model: {explanation.modelName}</p>
          </>
        ) : (
          <p style={{ color: 'var(--muted)' }}>
            No explanation yet. Click Regenerate or wait for the async AI job.
          </p>
        )}
      </section>

      {plan && (
        <section className="card" style={{ marginBottom: '1rem' }}>
          <h2>Execution assist plan</h2>
          <p className="disclaimer">{plan.disclaimer}</p>
          <ul>
            {plan.legs.map((leg, i) => (
              <li key={i}>
                <strong>{leg.sportsbookName}</strong>: {leg.outcomeLabel} @ {leg.decimalOdds} — stake $
                {leg.suggestedStake.toFixed(2)}
                {leg.deepLinkHint && (
                  <span style={{ color: 'var(--muted)' }}> ({leg.deepLinkHint})</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button className="primary" type="button" onClick={() => action('accepted')}>
          Accept (log)
        </button>
        <button type="button" onClick={() => action('skipped')}>
          Skip
        </button>
        <button type="button" onClick={() => action('executed')}>
          Mark filled
        </button>
      </div>
    </div>
  );
}
