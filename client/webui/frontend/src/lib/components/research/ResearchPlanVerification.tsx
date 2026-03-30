/**
 * Research Plan Verification Component
 *
 * Displays a research plan for user review before starting deep research.
 * Shows the plan title, steps, and provides Edit, Cancel, and Start buttons.
 * Includes a configurable auto-approve countdown timer on the Start button.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Brain, X, Pencil, Loader2, Plus, Trash2 } from "lucide-react";

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
    const [countdown, setCountdown] = useState(planData.auto_approve_seconds);
    const [isResponding, setIsResponding] = useState(false);
    const [hasResponded, setHasResponded] = useState(false);
    const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const hasRespondedRef = useRef(false);

    // Cleanup countdown on unmount
    useEffect(() => {
        return () => {
            if (countdownRef.current) {
                clearInterval(countdownRef.current);
            }
        };
    }, []);

    // Start countdown timer
    useEffect(() => {
        if (hasResponded || isEditing) return;

        countdownRef.current = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) {
                    // Auto-approve when countdown reaches 0
                    if (!hasRespondedRef.current) {
                        handleResponse("start", planData.steps);
                    }
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);

        return () => {
            if (countdownRef.current) {
                clearInterval(countdownRef.current);
            }
        };
    }, [hasResponded, isEditing]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleResponse = useCallback(
        async (action: "start" | "cancel", steps?: string[]) => {
            if (hasRespondedRef.current) return;
            hasRespondedRef.current = true;
            setHasResponded(true);
            setIsResponding(true);

            // Stop countdown
            if (countdownRef.current) {
                clearInterval(countdownRef.current);
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
        // Pause countdown while editing
        if (countdownRef.current) {
            clearInterval(countdownRef.current);
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

    // Calculate countdown progress for circular indicator
    const TIMER_RADIUS = 14;
    const circumference = 2 * Math.PI * TIMER_RADIUS;
    const countdownProgress = (countdown / planData.auto_approve_seconds) * 100;
    const strokeDashoffset = circumference - (countdownProgress / 100) * circumference;

    if (hasResponded && !isResponding) {
        return null; // Hide after response is sent
    }

    return (
        <div className="my-4">
            <div className="rounded-lg border bg-(--background-w10) p-4">
                {/* Title */}
                <div className="mb-4 flex items-start gap-3">
                    <div className="mt-0.5 flex-shrink-0 text-(--primary-wMain)">
                        <Brain className="h-5 w-5" />
                    </div>
                    <h3 className="text-base font-semibold">{planData.title}</h3>
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
                <div className="flex items-center justify-between">
                    <div>
                        {!isEditing && !hasResponded && (
                            <Button variant="outline" size="sm" onClick={handleEdit} disabled={isResponding}>
                                <Pencil className="mr-1.5 h-3.5 w-3.5" />
                                Edit
                            </Button>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        {!hasResponded && (
                            <Button variant="outline" size="sm" onClick={handleCancel} disabled={isResponding}>
                                <X className="mr-1.5 h-3.5 w-3.5" />
                                Cancel
                            </Button>
                        )}

                        {!hasResponded && (
                            <button
                                onClick={handleStart}
                                disabled={isResponding}
                                className="inline-flex items-center gap-2 rounded-full bg-(--primary-wMain) px-4 py-2 text-sm font-medium text-(--primary-text-on-wMain) transition-colors hover:opacity-90 disabled:opacity-50"
                            >
                                {isResponding ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <>
                                        Start
                                        {/* Countdown circle with number */}
                                        {!isEditing && countdown > 0 && (
                                            <span className="relative inline-flex h-8 w-8 items-center justify-center">
                                                <svg width="32" height="32" viewBox="0 0 32 32" className="-rotate-90">
                                                    {/* Background circle */}
                                                    <circle cx="16" cy="16" r={TIMER_RADIUS} fill="none" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                                                    {/* Progress circle */}
                                                    <circle
                                                        cx="16"
                                                        cy="16"
                                                        r={TIMER_RADIUS}
                                                        fill="none"
                                                        stroke="currentColor"
                                                        strokeWidth="2"
                                                        strokeDasharray={circumference}
                                                        strokeDashoffset={strokeDashoffset}
                                                        strokeLinecap="round"
                                                        className="transition-all duration-1000 ease-linear"
                                                    />
                                                </svg>
                                                <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold">{countdown}</span>
                                            </span>
                                        )}
                                    </>
                                )}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ResearchPlanVerification;
