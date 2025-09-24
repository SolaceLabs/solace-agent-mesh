import React from "react";
import { Check } from "lucide-react";

interface Step {
    title: string;
    description: string;
    completed: boolean;
}

interface StepIndicatorProps {
    currentStep: number;
    totalSteps: number;
    steps: Step[];
}

export const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep, totalSteps, steps }) => {
    return (
        <div className="w-full py-6">
            <div className="flex items-center justify-between">
                {steps.map((step, index) => {
                    const stepNumber = index + 1;
                    const isActive = stepNumber === currentStep;
                    const isCompleted = step.completed;

                    return (
                        <div key={stepNumber} className="flex items-center flex-1">
                            {/* Step Circle */}
                            <div className="flex items-center">
                                <div
                                    className={`
                                        flex h-10 w-10 items-center justify-center rounded-full border-2 text-sm font-semibold
                                        ${
                                            isCompleted
                                                ? "border-primary bg-primary text-primary-foreground"
                                                : isActive
                                                ? "border-primary bg-background text-primary"
                                                : "border-muted-foreground/30 bg-background text-muted-foreground"
                                        }
                                    `}
                                >
                                    {isCompleted ? <Check className="h-5 w-5" /> : stepNumber}
                                </div>
                                <div className="ml-4 min-w-0 flex-1">
                                    <p
                                        className={`text-sm font-medium ${
                                            isActive ? "text-foreground" : isCompleted ? "text-foreground" : "text-muted-foreground"
                                        }`}
                                    >
                                        {step.title}
                                    </p>
                                    <p className="text-xs text-muted-foreground">{step.description}</p>
                                </div>
                            </div>

                            {/* Connector Line */}
                            {stepNumber < totalSteps && (
                                <div className="flex-1 mx-4">
                                    <div
                                        className={`h-0.5 ${
                                            stepNumber < currentStep || isCompleted ? "bg-primary" : "bg-muted-foreground/30"
                                        }`}
                                    />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
