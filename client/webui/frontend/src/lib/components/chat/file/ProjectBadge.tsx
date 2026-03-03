import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";

interface ProjectBadgeProps {
    text?: string;
    className?: string;
    minWidth?: string;
    maxWidth?: string;
}

export const ProjectBadge = ({ text = "Unknown Project", className = "", minWidth = "24px", maxWidth = "120px" }: ProjectBadgeProps) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="default" className={`shrink ${className}`} style={{ minWidth, maxWidth }}>
                    <span className="block truncate font-semibold">{text}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent className="max-w-[480px]">
                <span className="block truncate">
                    Indexed from project <span className="font-semibold">{text}</span>
                </span>
            </TooltipContent>
        </Tooltip>
    );
};
