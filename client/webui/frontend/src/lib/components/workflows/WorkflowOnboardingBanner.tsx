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
        <div className="relative mx-6 mt-6 rounded-lg border border-(--color-learning-w20) bg-(--color-learning-w10) p-4">
            <Button variant="ghost" size="icon" onClick={handleDismiss} className="absolute top-2 right-2 h-6 w-6" aria-label="Dismiss banner">
                <X size={16} />
            </Button>

            <div className="pr-8">
                <p className="text-sm">
                    <span className="font-semibold">Workflows</span> can automate complex multi-agent tasks by orchestrating agents in a defined sequence. Define your workflows in YAML and deploy them to the Agent Mesh.
                </p>

                <a href="#" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-(--color-primary-wMain) hover:underline font-semibold">
                    Learn how to create workflows
                    <ExternalLink size={14} />
                </a>
            </div>
        </div>
    );
};
