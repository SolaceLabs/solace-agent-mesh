import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";

export const ProjectBadge = ({ text = "Project", className = "" }: { text?: string; className?: string }) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="default" className={`max-w-[120px] ${className}`}>
                    <span className="block truncate font-semibold">{text}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{text}</TooltipContent>
        </Tooltip>
    );
};
