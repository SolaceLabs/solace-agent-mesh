import React from "react";
import { Network } from "lucide-react";
import { Button } from "./button";

interface ViewWorkflowButtonProps {
    onClick: () => void;
    text?: string;
}

export const ViewWorkflowButton: React.FC<ViewWorkflowButtonProps> = ({ onClick, text = "View Agent Workflow" }) => {
    return (
        <Button data-testid="viewAgentWorkflow" variant="ghost" size="sm" onClick={onClick} tooltip={text}>
            <Network className="h-4 w-4" />
        </Button>
    );
};
