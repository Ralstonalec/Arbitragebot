import type { ArbitrageOpportunityDto, ExecutionPlan } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export async function fetchOpportunities(params?: {
  minEdgePct?: number;
  marketType?: string;
  status?: string;
}): Promise<ArbitrageOpportunityDto[]> {
  const q = new URLSearchParams();
  if (params?.minEdgePct != null) q.set('minEdgePct', String(params.minEdgePct));
  if (params?.marketType) q.set('marketType', params.marketType);
  if (params?.status) q.set('status', params.status);
  const res = await fetch(`${API_URL}/opportunities?${q}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to load opportunities');
  const data = await res.json();
  return data.items;
}

export async function fetchOpportunity(id: string) {
  const res = await fetch(`${API_URL}/opportunities/${id}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Not found');
  return res.json() as Promise<{
    opportunity: ArbitrageOpportunityDto;
    explanation: { briefText: string; detailedText: string; modelName: string } | null;
  }>;
}

export async function fetchExecutionPlan(id: string): Promise<ExecutionPlan> {
  const res = await fetch(`${API_URL}/opportunities/${id}/execution-plan`);
  if (!res.ok) throw new Error('Failed to load execution plan');
  return res.json();
}

export async function postOpportunityAction(
  id: string,
  actionType: string,
  metadata?: Record<string, unknown>,
) {
  const res = await fetch(`${API_URL}/opportunities/${id}/actions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ actionType, metadata }),
  });
  return res.json();
}

export async function queueExplanation(id: string) {
  await fetch(`${API_URL}/opportunities/${id}/explain`, { method: 'POST' });
}
