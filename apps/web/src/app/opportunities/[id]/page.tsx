import OpportunityDetailClient from './client';

/** Placeholder path for static export; real IDs load client-side via API */
export function generateStaticParams() {
  return [{ id: '_' }];
}

export default function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <OpportunityDetailPageInner params={params} />;
}

async function OpportunityDetailPageInner({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OpportunityDetailClient id={id} />;
}
