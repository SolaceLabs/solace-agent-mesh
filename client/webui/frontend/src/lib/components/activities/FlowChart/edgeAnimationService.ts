import type { VisualizerStep } from "@/lib/types";

export interface EdgeAnimationState {
    isAnimated: boolean;
    animationType: "request" | "response" | "static";
}

export class EdgeAnimationService {
    /**
     * Simplified animation logic: Only animate agent-to-tool request edges
     * until their corresponding response is received.
     */
    public getEdgeAnimationState(edgeStepId: string, upToStep: number, allSteps: VisualizerStep[]): EdgeAnimationState {
        const currentStep = allSteps.find(step => step.id === edgeStepId);
        if (!currentStep) {
            return { isAnimated: false, animationType: "static" };
        }

        // Only animate agent-to-tool interactions
        if (!this.isAgentToToolRequest(currentStep)) {
            return { isAnimated: false, animationType: "static" };
        }

        // Check if this request has been completed by looking at steps up to current point
        const stepsUpToPoint = allSteps.slice(0, upToStep + 1);
        const isCompleted = this.hasMatchingResponse(currentStep, stepsUpToPoint);

        if (isCompleted) {
            return { isAnimated: false, animationType: "static" };
        }

        return {
            isAnimated: true,
            animationType: "request",
        };
    }

    /**
     * Check if a step represents an agent-to-tool request that should be animated
     */
    private isAgentToToolRequest(step: VisualizerStep): boolean {
        switch (step.type) {
            case "AGENT_LLM_CALL":
                // Agent calling LLM (lane 2 to lane 3)
                return true;

            case "AGENT_TOOL_INVOCATION_START": {
                // Only animate if it's a tool call, not a peer delegation
                const isPeerDelegation = step.data.toolDecision?.isPeerDelegation || step.data.toolInvocationStart?.isPeerInvocation || (step.target && step.target.startsWith("peer_"));
                return !isPeerDelegation;
            }

            default:
                return false;
        }
    }

    /**
     * Check if there's a matching response for the given request step
     */
    private hasMatchingResponse(requestStep: VisualizerStep, stepsToCheck: VisualizerStep[]): boolean {
        switch (requestStep.type) {
            case "AGENT_LLM_CALL":
                return this.hasLLMResponse(requestStep, stepsToCheck);

            case "AGENT_TOOL_INVOCATION_START":
                return this.hasToolResponse(requestStep, stepsToCheck);

            default:
                return false;
        }
    }

    /**
     * Check if there's an LLM response for the given LLM call
     */
    private hasLLMResponse(llmCallStep: VisualizerStep, stepsToCheck: VisualizerStep[]): boolean {
        const callTimestamp = new Date(llmCallStep.timestamp).getTime();
        const callingAgent = llmCallStep.source;

        // Look for any step that comes after this LLM call from the same agent
        // This indicates the LLM call has completed and the agent is proceeding
        return stepsToCheck.some(step => {
            const stepTimestamp = new Date(step.timestamp).getTime();

            if (stepTimestamp < callTimestamp) return false;

            // Check for direct LLM responses to the agent
            const isDirectLLMResponse = (step.type === "AGENT_LLM_RESPONSE_TOOL_DECISION" || step.type === "AGENT_LLM_RESPONSE_TO_AGENT") && step.target === callingAgent;

            // Check for any subsequent action by the same agent (indicates LLM call completed)
            const isSubsequentAgentAction = step.source === callingAgent && (step.type === "AGENT_TOOL_INVOCATION_START" || step.type === "TASK_COMPLETED");
            const isPeerResponse = step.type === "AGENT_TOOL_EXECUTION_RESULT" && step.data.toolResult?.isPeerResponse;

            return isDirectLLMResponse || isSubsequentAgentAction || isPeerResponse;
        });
    }

    /**
     * Check if there's a tool response for the given tool invocation
     */
    private hasToolResponse(toolCallStep: VisualizerStep, stepsToCheck: VisualizerStep[]): boolean {
        const callTimestamp = new Date(toolCallStep.timestamp).getTime();
        const toolName = toolCallStep.target;
        const callingAgent = toolCallStep.source;

        return stepsToCheck.some(step => {
            const stepTimestamp = new Date(step.timestamp).getTime();
            if (stepTimestamp < callTimestamp) return false;

            return step.type === "AGENT_TOOL_EXECUTION_RESULT" && step.source === toolName && step.target === callingAgent;
        });
    }

    public isRequestStep(step: VisualizerStep): boolean {
        return this.isAgentToToolRequest(step);
    }

    public isResponseStep(step: VisualizerStep): boolean {
        return ["AGENT_TOOL_EXECUTION_RESULT", "AGENT_LLM_RESPONSE_TOOL_DECISION", "AGENT_LLM_RESPONSE_TO_AGENT"].includes(step.type);
    }
}
