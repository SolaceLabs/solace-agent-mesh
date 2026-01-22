import React, { useState, useEffect } from "react";

import { X, ExternalLink } from "lucide-react";
import { Button } from "@/lib/components/ui/button";

const STORAGE_KEY = "workflow-onboarding-dismissed";

export const WorkflowOnboardingBanner: React.FC = () => {
    const [isDismissed, setIsDismissed] = useState<boolean>(true);

    useEffect(() => {
        const dismissed = localStorage.getItem(STORAGE_KEY);
        setIsDismissed(dismissed === "true");
    }, []);

    const handleDismiss = () => {
        localStorage.setItem(STORAGE_KEY, "true");
        setIsDismissed(true);
    };

    if (isDismissed) {
        return null;
    }

    return (
        <div className="relative mx-6 mt-6 rounded-lg border border-(--color-learning-w20) dark:border-(--color-learning-w90) bg-(--color-learning-w10) dark:bg-(--color-learning-wMain) p-4">
            <Button variant="ghost" size="icon" onClick={handleDismiss} tooltip="Close" className="absolute top-2 right-2 h-6 w-6">
                <X size={16} />
            </Button>

            <div className="pr-8">
                <p className="text-sm">
                    <span className="font-semibold">Turn complex multi-agent tasks into streamlined workflows. </span>Define the sequence in YAML, deploy to Agent Mesh, and watch your workflow handle the coordination automatically. Great for building repeatable processes that need multiple agents working together in a specific order.
                </p>

                <Button variant="link" className="mt-2 h-auto !pl-0 !pr-0 text-sm hover:underline" asChild>
                    <a href="#">
                        Learn how to create workflows
                        <ExternalLink size={14} />
                    </a>
                </Button>
            </div>
        </div>
    );
};
