import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";

export const ProjectBadge = ({ text = "Project", className = "" }: { text?: string; className?: string }) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="outline" className={`max-w-[120px] ${className}`}>
                    <span className="block truncate">{text}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{text}</TooltipContent>
        </Tooltip>
    );
};
