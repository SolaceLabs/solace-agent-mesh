import React from "react";
import { MessageLoading, ViewWorkflowButton } from "@/lib/components/ui";

interface LoadingMessageRowProps {
    statusText?: string;
    onViewWorkflow?: () => void;
}

const BreathingDot = () => <span className="brand-breathe mr-3 ml-2 inline-block size-7 rounded-full bg-(--brand-wMain)" aria-label="Waiting for response" />;

export const LoadingMessageRow = React.memo<LoadingMessageRowProps>(({ statusText, onViewWorkflow }) => {
    const indicator = onViewWorkflow ? <ViewWorkflowButton onClick={onViewWorkflow} /> : statusText ? <MessageLoading className="mr-3 ml-2" /> : <BreathingDot />;
    return (
        <div className="flex min-h-8 items-center space-x-3 py-1">
            {indicator}
            <div className="flex min-w-0 flex-1 items-center gap-1">
                {statusText && (
                    <span className="animate-pulse truncate text-sm text-(--secondary-text-wMain)" title={statusText}>
                        {statusText}
                    </span>
                )}
            </div>
        </div>
    );
});
