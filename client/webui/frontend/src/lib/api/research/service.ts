import { api } from "@/lib/api/client";

// Only the approval ("start") path uses this endpoint. Cancellation is handled
// by the standard tasks/:cancel flow (same as the chat stop button) so the
// orchestrator is terminated deterministically rather than relying on the LLM
// to refrain from re-invoking the tool after a cooperative signal.
export interface SubmitPlanResponseInput {
    planId: string;
    agentName: string;
    steps?: string[];
}

export const submitPlanResponse = async ({ planId, agentName, steps }: SubmitPlanResponseInput): Promise<void> => {
    await api.webui.post("/api/v1/research/plan-response", {
        planId,
        agentName,
        action: "start",
        steps,
    });
};
