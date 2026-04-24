import { useCallback, useState } from "react";
import { Brain, Loader2, Plus, Trash2, Play } from "lucide-react";

import { useSubmitPlanResponse } from "@/lib/api";
import { Button } from "@/lib/components/ui/button";
import { Input } from "@/lib/components/ui/input";
import { useChatContext } from "@/lib/hooks";
import type { DataPart } from "@/lib/types";

const DashedCircle = ({ className }: { className?: string }) => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={className}>
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" strokeLinecap="round" />
    </svg>
);

export interface ResearchPlanData {
    type: "deep_research_plan";
    plan_id: string;
    title: string;
    research_question: string;
    steps: string[];
    research_type: string;
    max_iterations: number;
    max_runtime_seconds: number;
    sources: string[];
    // Persisted once the user confirms/cancels so reloading the session
    // doesn't show an interactive prompt that has no live backend listener.
    responded?: "start" | "cancel";
}

interface ResearchPlanVerificationProps {
    planData: ResearchPlanData;
}

export const ResearchPlanVerification = ({ planData }: ResearchPlanVerificationProps) => {
    const { setMessages, displayError } = useChatContext();
    const { mutateAsync: submitPlanResponse, isPending } = useSubmitPlanResponse();

    const [isEditing, setIsEditing] = useState(false);
    const [editedSteps, setEditedSteps] = useState<string[]>(planData.steps);

    const markResponded = useCallback(
        (action: "start" | "cancel") => {
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

    const handleResponse = useCallback(
        async (action: "start" | "cancel", steps?: string[]) => {
            if (planData.responded) return;
            try {
                await submitPlanResponse({
                    planId: planData.plan_id,
                    action,
                    steps: action === "start" ? (steps ?? planData.steps) : undefined,
                });
                markResponded(action);
            } catch (error) {
                displayError({
                    title: "Research plan response failed",
                    error: error instanceof Error ? error.message : "Unable to submit research plan response.",
                });
            }
        },
        [planData.plan_id, planData.responded, planData.steps, submitPlanResponse, markResponded, displayError]
    );

    const handleStart = () => handleResponse("start", isEditing ? editedSteps : planData.steps);
    const handleCancel = () => handleResponse("cancel");

    const handleEdit = () => {
        setIsEditing(true);
        setEditedSteps([...planData.steps]);
    };

    const handleStepChange = (index: number, value: string) => {
        const newSteps = [...editedSteps];
        newSteps[index] = value;
        setEditedSteps(newSteps);
    };

    const handleAddStep = () => setEditedSteps([...editedSteps, ""]);

    const handleRemoveStep = (index: number) => {
        if (editedSteps.length <= 1) return;
        setEditedSteps(editedSteps.filter((_, i) => i !== index));
    };

    if (planData.responded) {
        return null;
    }

    return (
        <div className="my-4">
            <div className="rounded-lg border bg-(--background-w10) p-4">
                <div className="mb-4 flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                        <div className="mt-0.5 flex-shrink-0 text-(--primary-wMain)">
                            <Brain className="h-5 w-5" />
                        </div>
                        <h3 className="text-base font-semibold">
                            <span className="font-normal text-(--secondary-text-wMain)">Research Plan: </span>
                            {planData.title}
                        </h3>
                    </div>
                    {!isEditing && (
                        <Button variant="ghost" size="sm" onClick={handleEdit} disabled={isPending} className="flex-shrink-0 text-sm">
                            Edit
                        </Button>
                    )}
                </div>

                <div className="mb-5 space-y-3 pl-2">
                    {(isEditing ? editedSteps : planData.steps).map((step, index) => (
                        <div key={index} className="flex items-start gap-3">
                            {isEditing ? (
                                <>
                                    <span className="mt-2.5 w-4 flex-shrink-0 text-center text-xs font-medium text-(--secondary-text-wMain)">{index + 1}</span>
                                    <Input type="text" value={step} onChange={e => handleStepChange(index, e.target.value)} placeholder="Describe a research step..." className="flex-1" />
                                    <Button variant="ghost" size="icon" onClick={() => handleRemoveStep(index)} disabled={editedSteps.length <= 1} className="flex-shrink-0">
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <div className="mt-0.5 flex-shrink-0">
                                        <DashedCircle className="text-(--secondary-text-wMain)" />
                                    </div>
                                    <span className="text-sm leading-relaxed">{step}</span>
                                </>
                            )}
                        </div>
                    ))}

                    {isEditing && (
                        <Button variant="ghost" size="sm" onClick={handleAddStep} className="ml-7 text-xs">
                            <Plus className="mr-1 h-3 w-3" />
                            Add step
                        </Button>
                    )}
                </div>

                <div className="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={handleCancel} disabled={isPending}>
                        Cancel
                    </Button>
                    <Button size="sm" onClick={handleStart} disabled={isPending}>
                        {isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <>
                                <Play className="mr-1.5 h-3.5 w-3.5" />
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
