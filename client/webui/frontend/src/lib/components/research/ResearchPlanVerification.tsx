import { useCallback, useState, useSyncExternalStore } from "react";
import { Brain, CircleDashed, Loader2, Pencil, Plus, Trash2, Play } from "lucide-react";

import { useSubmitPlanResponse } from "@/lib/api";
import { Button } from "@/lib/components/ui/button";
import { Input } from "@/lib/components/ui/input";
import { useChatContext } from "@/lib/hooks";
import type { DataPart } from "@/lib/types";
import { uuid } from "@/lib/utils/uuid";

import { getRespondedPlansSnapshot, markPlanResponded, subscribeRespondedPlans } from "./respondedPlansStore";

export interface ResearchPlanData {
    type: "deep_research_plan";
    plan_id: string;
    // Name of the agent whose tool is waiting for this response. Echoed in
    // the plan-response POST so the gateway can route the control signal to
    // the right agent (deep research may run on a delegated peer agent).
    agent_name: string;
    title: string;
    research_question: string;
    steps: string[];
    research_type: string;
    max_iterations: number;
    max_runtime_seconds: number;
    sources: string[];
    // Set once the user confirms/cancels (optimistic) or once a stale signal
    // arrives from the backend.
    responded?: "start" | "cancel" | "stale";
}

interface ResearchPlanVerificationProps {
    planData: ResearchPlanData;
}

interface EditableStep {
    id: string;
    value: string;
}

const makeStepId = () => uuid();

const toEditableSteps = (steps: string[]): EditableStep[] => steps.map(value => ({ id: makeStepId(), value }));

export const ResearchPlanVerification = ({ planData }: ResearchPlanVerificationProps) => {
    const { setMessages, displayError, handleCancel: cancelCurrentTask } = useChatContext();
    const { mutateAsync: submitPlanResponse, isPending } = useSubmitPlanResponse();

    const [isEditing, setIsEditing] = useState(false);
    const [editedSteps, setEditedSteps] = useState<EditableStep[]>(() => toEditableSteps(planData.steps));

    // Consult the session-local store so re-delivered plan events cannot
    // resurrect a card the user has already answered.
    const respondedMap = useSyncExternalStore(subscribeRespondedPlans, getRespondedPlansSnapshot, getRespondedPlansSnapshot);
    const sessionResponded = respondedMap.get(planData.plan_id);

    const markResponded = useCallback(
        (action: "start" | "cancel") => {
            markPlanResponded(planData.plan_id, action);
            setMessages(prev =>
                prev.map(msg => {
                    if (!msg.parts) return msg;
                    let changed = false;
                    const nextParts = msg.parts.map(part => {
                        if (part.kind !== "data") return part;
                        const dataPart = part as DataPart;
                        const data = dataPart.data as Partial<ResearchPlanData> | undefined;
                        if (data?.type !== "deep_research_plan" || data.plan_id !== planData.plan_id) return part;
                        changed = true;
                        return { ...dataPart, data: { ...data, responded: action } };
                    });
                    return changed ? { ...msg, parts: nextParts } : msg;
                })
            );
        },
        [planData.plan_id, setMessages]
    );

    const handleStart = useCallback(
        async (steps?: string[]) => {
            if (planData.responded || sessionResponded) return;
            try {
                await submitPlanResponse({
                    planId: planData.plan_id,
                    agentName: planData.agent_name,
                    steps: steps ?? planData.steps,
                });
                markResponded("start");
            } catch (error) {
                displayError({
                    title: "Research plan response failed",
                    error: error instanceof Error ? error.message : "Unable to submit research plan response.",
                });
            }
        },
        [planData.plan_id, planData.agent_name, planData.responded, planData.steps, sessionResponded, submitPlanResponse, markResponded, displayError]
    );

    // Cancel must match the chat-input stop button: cancel the orchestrator
    // task, which cascades to the peer running the research. The peer's
    // tool unwinds via asyncio cancellation - no plan-response POST needed.
    // Relying on the LLM to stop after a cancel is not robust (the
    // orchestrator has been observed re-invoking deep_research anyway), so
    // we short-circuit at the task level.
    const handlePlanCancel = useCallback(() => {
        if (planData.responded || sessionResponded) return;
        markResponded("cancel");
        try {
            cancelCurrentTask();
        } catch (error) {
            displayError({
                title: "Task cancellation failed",
                error: error instanceof Error ? error.message : "Unable to cancel the research task.",
            });
        }
    }, [planData.responded, sessionResponded, markResponded, cancelCurrentTask, displayError]);

    const handleStartClick = () => handleStart(isEditing ? editedSteps.map(s => s.value) : planData.steps);

    const handleEdit = () => {
        setEditedSteps(toEditableSteps(planData.steps));
        setIsEditing(true);
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditedSteps(toEditableSteps(planData.steps));
    };

    const handleStepChange = (id: string, value: string) => {
        setEditedSteps(prev => prev.map(step => (step.id === id ? { ...step, value } : step)));
    };

    const handleAddStep = () => setEditedSteps(prev => [...prev, { id: makeStepId(), value: "" }]);

    const handleRemoveStep = (id: string) => {
        setEditedSteps(prev => (prev.length <= 1 ? prev : prev.filter(step => step.id !== id)));
    };

    if (planData.responded || sessionResponded) {
        return null;
    }

    return (
        <div className="my-4">
            <div className="rounded-lg border bg-(--background-w10) p-4">
                <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                        <div className="mt-0.5 flex-shrink-0 text-(--primary-wMain)" aria-hidden="true">
                            <Brain className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                            <h3 className="text-base font-semibold">
                                <span className="font-normal text-(--secondary-text-wMain)">Research Plan: </span>
                                {planData.title}
                            </h3>
                            {planData.research_question && <p className="mt-1 text-sm text-(--secondary-text-wMain)">{planData.research_question}</p>}
                        </div>
                    </div>
                    {!isEditing && (
                        <Button variant="ghost" size="sm" onClick={handleEdit} disabled={isPending} className="flex-shrink-0 text-sm">
                            <Pencil className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                            Edit
                        </Button>
                    )}
                </div>

                <div className="mb-5 space-y-3 pl-2">
                    {isEditing
                        ? editedSteps.map((step, index) => (
                              <div key={step.id} className="flex items-start gap-3">
                                  <span className="mt-2.5 w-4 flex-shrink-0 text-center text-xs font-medium text-(--secondary-text-wMain)">{index + 1}</span>
                                  <Input type="text" value={step.value} onChange={e => handleStepChange(step.id, e.target.value)} placeholder="Describe a research step..." className="flex-1" aria-label={`Research step ${index + 1}`} />
                                  <Button variant="ghost" size="icon" onClick={() => handleRemoveStep(step.id)} disabled={editedSteps.length <= 1} className="flex-shrink-0" aria-label={`Remove step ${index + 1}`}>
                                      <Trash2 className="h-4 w-4" />
                                  </Button>
                              </div>
                          ))
                        : planData.steps.map((step, index) => (
                              <div key={index} className="flex items-start gap-3">
                                  <div className="mt-0.5 flex-shrink-0" aria-hidden="true">
                                      <CircleDashed className="h-4 w-4 text-(--secondary-text-wMain)" />
                                  </div>
                                  <span className="text-sm leading-relaxed">{step}</span>
                              </div>
                          ))}

                    {isEditing && (
                        <Button variant="ghost" size="sm" onClick={handleAddStep} className="ml-7 text-xs">
                            <Plus className="mr-1 h-3 w-3" aria-hidden="true" />
                            Add step
                        </Button>
                    )}
                </div>

                <div className="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={handlePlanCancel} disabled={isPending}>
                        Cancel Research
                    </Button>
                    {isEditing && (
                        <Button variant="outline" size="sm" onClick={handleCancelEdit} disabled={isPending}>
                            Discard Changes
                        </Button>
                    )}
                    <Button size="sm" onClick={handleStartClick} disabled={isPending} aria-label="Start">
                        {isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        ) : (
                            <>
                                <Play className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                                Start
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default ResearchPlanVerification;
