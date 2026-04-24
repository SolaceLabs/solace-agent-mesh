import { api } from "@/lib/api/client";

export interface SubmitPlanResponseInput {
    planId: string;
    action: "start" | "cancel";
    steps?: string[];
}

export const submitPlanResponse = async ({ planId, action, steps }: SubmitPlanResponseInput): Promise<void> => {
    await api.webui.post("/api/v1/research/plan-response", {
        planId,
        action,
        steps: action === "start" ? steps : undefined,
    });
};
