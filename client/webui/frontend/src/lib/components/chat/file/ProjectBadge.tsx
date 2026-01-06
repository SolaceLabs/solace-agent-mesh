import { Badge, Tooltip, TooltipContent, TooltipTrigger } from "@/lib";

export const ProjectBadge = ({ text = "Project" }: { text?: string }) => {
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Badge variant="outline" className="max-w-[120px]">
                    <span className="block truncate">{text}</span>
                </Badge>
            </TooltipTrigger>
            <TooltipContent>{text}</TooltipContent>
        </Tooltip>
    );
};
