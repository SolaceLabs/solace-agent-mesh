import type { FC } from "react";
import { FileText, Wrench } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import type { LayoutNode } from "../utils/types";

interface ToolNodeProps {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const ToolNode: FC<ToolNodeProps> = ({ node, isSelected, onClick }) => {
    const isProcessing = node.data.status === "in-progress";
    const haloClass = isProcessing ? 'processing-halo' : '';
    const artifactCount = node.data.createdArtifacts?.length || 0;

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <div
                    className={`cursor-pointer rounded-lg border-2 border-(--color-accent-n7-w100) bg-(--color-background-w10) px-3 py-2 text-(--color-primary-text-wMain) shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-(--color-accent-n7-wMain) dark:bg-(--color-background-wMain) dark:text-(--color-primary-text-w10) ${
                        isSelected ? "ring-2 ring-blue-500" : ""
                    } ${haloClass}`}
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    <div className="flex items-center justify-center gap-2">
                        <Wrench className="h-3.5 w-3.5 flex-shrink-0 text-(--color-accent-n7-w100) dark:text-(--color-accent-n7-wMain)" />
                        <div className="text-sm truncate">{node.data.label}</div>
                        {artifactCount > 0 && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span className="flex items-center gap-0.5 rounded-full bg-(--color-accent-n1-w10) px-1 py-0.5 text-[10px] font-medium text-(--color-accent-n1-w100) dark:bg-(--color-accent-n1-w100)/30 dark:text-(--color-accent-n1-w30)">
                                        <FileText className="h-2.5 w-2.5" />
                                        {artifactCount}
                                    </span>
                                </TooltipTrigger>
                                <TooltipContent>{`${artifactCount} ${artifactCount === 1 ? 'artifact' : 'artifacts'} created`}</TooltipContent>
                            </Tooltip>
                        )}
                    </div>
                </div>
            </TooltipTrigger>
            {node.data.description && (
                <TooltipContent>{node.data.description}</TooltipContent>
            )}
        </Tooltip>
    );
};

export default ToolNode;
