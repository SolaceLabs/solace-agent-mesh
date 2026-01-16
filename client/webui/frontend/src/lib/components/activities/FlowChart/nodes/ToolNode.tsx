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
                    className={`cursor-pointer rounded-lg border-2 border-cyan-600 bg-white px-3 py-2 text-gray-800 shadow-md transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-xl dark:border-cyan-400 dark:bg-gray-800 dark:text-gray-200 ${
                        isSelected ? "ring-2 ring-blue-500" : ""
                    } ${haloClass}`}
                    onClick={(e) => {
                        e.stopPropagation();
                        onClick?.(node);
                    }}
                >
                    <div className="flex items-center justify-center gap-2">
                        <Wrench className="h-3.5 w-3.5 flex-shrink-0 text-cyan-600 dark:text-cyan-400" />
                        <div className="text-sm truncate">{node.data.label}</div>
                        {artifactCount > 0 && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <span className="flex items-center gap-0.5 rounded-full bg-indigo-100 px-1 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300">
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
