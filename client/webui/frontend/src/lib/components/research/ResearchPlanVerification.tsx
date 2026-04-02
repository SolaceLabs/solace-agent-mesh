/**
 * Research Plan Verification Component
 *
 * Displays a research plan for user review before starting deep research.
 * Shows the plan title, steps, and provides Edit, Cancel, and Start buttons.
 * Includes a configurable auto-approve countdown timer on the Start button.
 */

import React, { useState, useCallback, useRef } from "react";
import { Brain, Loader2, Plus, Trash2, Play } from "lucide-react";

/** Dashed circle icon matching the screenshot's "pending step" indicator */
const DashedCircle: React.FC<{ className?: string }> = ({ className }) => (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={className}>
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" strokeLinecap="round" />
    </svg>
);
import { Button } from "@/lib/components/ui/button";
import { api } from "@/lib/api";

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
    auto_approve_seconds: number;
}

interface ResearchPlanVerificationProps {
    planData: ResearchPlanData;
    onResponded?: (action: "start" | "cancel") => void;
}

export const ResearchPlanVerification: React.FC<ResearchPlanVerificationProps> = ({ planData, onResponded }) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editedSteps, setEditedSteps] = useState<string[]>(planData.steps);
    const [isResponding, setIsResponding] = useState(false);
    const [hasResponded, setHasResponded] = useState(false);
    const hasRespondedRef = useRef(false);
    const autoApproveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Auto-approve after timeout (disabled for now - user must explicitly confirm)
    // Uncomment to re-enable auto-approve behavior:
    // useEffect(() => {
    //     if (hasResponded || isEditing) return;
    //     autoApproveRef.current = setTimeout(() => {
    //         if (!hasRespondedRef.current) {
    //             handleResponse("start", planData.steps);
    //         }
    //     }, planData.auto_approve_seconds * 1000);
    //     return () => {
    //         if (autoApproveRef.current) {
    //             clearTimeout(autoApproveRef.current);
    //         }
    //     };
    // }, [hasResponded, isEditing]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleResponse = useCallback(
        async (action: "start" | "cancel", steps?: string[]) => {
            if (hasRespondedRef.current) return;
            hasRespondedRef.current = true;
            setHasResponded(true);
            setIsResponding(true);

            // Stop auto-approve timer
            if (autoApproveRef.current) {
                clearTimeout(autoApproveRef.current);
            }

            try {
                await api.webui.post("/api/v1/research/plan-response", {
                    planId: planData.plan_id,
                    action,
                    steps: action === "start" ? steps || planData.steps : undefined,
                });
            } catch (error) {
                console.error("[ResearchPlanVerification] Error sending plan response:", error);
            } finally {
                setIsResponding(false);
                onResponded?.(action);
            }
        },
        [planData.plan_id, planData.steps, onResponded]
    );

    const handleStart = () => {
        handleResponse("start", isEditing ? editedSteps : planData.steps);
    };

    const handleCancel = () => {
        handleResponse("cancel");
    };

    const handleEdit = () => {
        // Pause auto-approve while editing
        if (autoApproveRef.current) {
            clearTimeout(autoApproveRef.current);
        }
        setIsEditing(true);
        setEditedSteps([...planData.steps]);
    };

    const handleStepChange = (index: number, value: string) => {
        const newSteps = [...editedSteps];
        newSteps[index] = value;
        setEditedSteps(newSteps);
    };

    const handleAddStep = () => {
        setEditedSteps([...editedSteps, ""]);
    };

    const handleRemoveStep = (index: number) => {
        if (editedSteps.length <= 1) return;
        const newSteps = editedSteps.filter((_, i) => i !== index);
        setEditedSteps(newSteps);
    };

    if (hasResponded && !isResponding) {
        return null; // Hide after response is sent
    }

    return (
        <div className="my-4">
            <div className="rounded-lg border bg-(--background-w10) p-4">
                {/* Title row with Edit button in top right */}
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
                    {!isEditing && !hasResponded && (
                        <Button variant="ghost" size="sm" onClick={handleEdit} disabled={isResponding} className="flex-shrink-0 text-sm">
                            Edit
                        </Button>
                    )}
                </div>

                {/* Steps */}
                <div className="mb-5 space-y-3 pl-2">
                    {(isEditing ? editedSteps : planData.steps).map((step, index) => (
                        <div key={index} className="flex items-start gap-3">
                            {isEditing ? (
                                <>
                                    <span className="mt-2.5 w-4 flex-shrink-0 text-center text-xs font-medium text-(--secondary-text-wMain)">{index + 1}</span>
                                    <input
                                        type="text"
                                        value={step}
                                        onChange={e => handleStepChange(index, e.target.value)}
                                        className="flex-1 rounded-md border bg-(--background-w10) px-3 py-2 text-sm focus:border-(--primary-wMain) focus:outline-none"
                                        placeholder="Describe a research step..."
                                    />
                                    <Button variant="ghost" size="icon" onClick={() => handleRemoveStep(index)} disabled={editedSteps.length <= 1} className="flex-shrink-0">
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </>
                            ) : (
                                <>
                                    {/* Dashed circle indicating pending step (matches screenshot) */}
                                    <div className="mt-0.5 flex-shrink-0">
                                        <DashedCircle className="text-(--secondary-text-wMain)" />
                                    </div>
                                    <span className="text-sm leading-relaxed">{step}</span>
                                </>
                            )}
                        </div>
                    ))}

                    {/* Add step button in edit mode */}
                    {isEditing && (
                        <Button variant="ghost" size="sm" onClick={handleAddStep} className="ml-7 text-xs">
                            <Plus className="mr-1 h-3 w-3" />
                            Add step
                        </Button>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex items-center justify-end gap-2">
                    {!hasResponded && (
                        <Button variant="ghost" size="sm" onClick={handleCancel} disabled={isResponding}>
                            Cancel
                        </Button>
                    )}

                    {!hasResponded && (
                        <Button size="sm" onClick={handleStart} disabled={isResponding}>
                            {isResponding ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <>
                                    <Play className="mr-1.5 h-3.5 w-3.5" />
                                    Start
                                </>
                            )}
                        </Button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ResearchPlanVerification;
