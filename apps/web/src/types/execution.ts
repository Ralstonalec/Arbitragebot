export interface ExecutionPlanLeg {
  sportsbookId: string;
  sportsbookName: string;
  sportsbookCode: string;
  outcomeLabel: string;
  marketType: string;
  decimalOdds: number;
  suggestedStake: number;
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
