import React from "react";
import { Network } from "lucide-react";
import { Button } from "./button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";
import { cn } from "@/lib/utils";

interface ViewWorkflowButtonProps {
    onClick: () => void;
    text?: string;
    className?: string;
}

export const ViewWorkflowButton: React.FC<ViewWorkflowButtonProps> = ({ 
    onClick, 
    text = "View Agent Workflow",
    className 
}) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClick}
                    className={cn(
                        "p-2", // Square padding for icon-only button
                        className
                    )}
                >
                    <Network className="h-4 w-4" />
                </Button>
            </TooltipTrigger>
            <TooltipContent>
                {text}
            </TooltipContent>
        </Tooltip>
    );
};
