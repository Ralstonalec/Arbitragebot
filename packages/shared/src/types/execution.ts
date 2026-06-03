/** Structured plan for user-side / browser execution — never auto-login server-side */
export interface ExecutionPlanLeg {
  sportsbookId: string;
  sportsbookName: string;
  sportsbookCode: string;
  outcomeLabel: string;
  marketType: string;
  decimalOdds: number;
  suggestedStake: number;
  /** Public deep-link slug or path hint — not credentials */
  deepLinkHint?: string;
  selectionIdentifier: string;
}

export interface ExecutionPlan {
  opportunityId: string;
  generatedAt: string;
  currency: string;
  totalStake: number;
  theoreticalMarginPct: number;
  legs: ExecutionPlanLeg[];
  disclaimer: string;
}
