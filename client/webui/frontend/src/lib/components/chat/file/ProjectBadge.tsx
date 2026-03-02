import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";

interface ProjectBadgeProps {
    text?: string;
    className?: string;
    projectName?: string;
    isDeleted?: boolean;
}

export const ProjectBadge = ({ text = "Project", className = "", projectName, isDeleted = false }: ProjectBadgeProps) => {
    const displayText = projectName || text;
    const tooltipText = isDeleted ? `Project "${projectName}" has been deleted` : displayText;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="default" className={`max-w-[120px] ${isDeleted ? "line-through opacity-50" : ""} ${className}`}>
                    <span className="block truncate font-semibold">{displayText}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{tooltipText}</TooltipContent>
        </Tooltip>
    );
};
