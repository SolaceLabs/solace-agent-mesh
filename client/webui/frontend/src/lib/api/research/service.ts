import { api } from "@/lib/api/client";

export interface SubmitPlanResponseInput {
    planId: string;
    agentName: string;
    action: "start" | "cancel";
    steps?: string[];
}

export const submitPlanResponse = async ({ planId, agentName, action, steps }: SubmitPlanResponseInput): Promise<void> => {
    await api.webui.post("/api/v1/research/plan-response", {
        planId,
        agentName,
        action,
        steps: action === "start" ? steps : undefined,
    });
};
